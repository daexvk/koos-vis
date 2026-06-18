from __future__ import annotations

import argparse
from dataclasses import dataclass
import fnmatch
import signal
import threading
import time
from pathlib import Path
from typing import Iterable

from app.core.config import get_settings
from app.services.subset_job_service import get_subset_job_status, start_subset_job


@dataclass(frozen=True)
class WatchOptions:
    input_root: Path
    debounce_seconds: float
    stable_seconds: float
    poll_interval_seconds: float
    patterns: tuple[str, ...]


class SubsetWatchService:
    def __init__(self, options: WatchOptions) -> None:
        self.options = options
        self._stop_event = threading.Event()
        self._changed_event = threading.Event()
        self._known_signatures: dict[Path, tuple[int, int]] = {}

    def run(self) -> None:
        if not self.options.input_root.exists():
            raise FileNotFoundError(f"subset watch input root not found: {self.options.input_root}")
        if not self.options.input_root.is_dir():
            raise NotADirectoryError(f"subset watch input root is not a directory: {self.options.input_root}")

        self._known_signatures = self._snapshot()
        print(f"[subset-watch] watching: {self.options.input_root}", flush=True)
        print(f"[subset-watch] patterns: {', '.join(self.options.patterns)}", flush=True)

        observer = self._start_watchdog_observer()
        if observer is None:
            print("[subset-watch] watchdog unavailable; using polling scanner", flush=True)
        else:
            print("[subset-watch] using watchdog observer", flush=True)

        try:
            while not self._stop_event.is_set():
                if observer is None:
                    self._poll_once()
                self._changed_event.wait(self.options.poll_interval_seconds)
                if not self._changed_event.is_set():
                    continue

                self._changed_event.clear()
                self._debounce()
                self._wait_for_stable_files()
                self._start_job_when_idle()
        finally:
            if observer is not None:
                observer.stop()
                observer.join(timeout=10)

    def stop(self) -> None:
        self._stop_event.set()
        self._changed_event.set()

    def _start_watchdog_observer(self):
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            return None

        service = self

        class Handler(FileSystemEventHandler):
            def on_any_event(self, event) -> None:
                if event.is_directory:
                    return
                paths = [Path(event.src_path)]
                dest_path = getattr(event, "dest_path", None)
                if dest_path:
                    paths.append(Path(dest_path))
                if any(service._matches(path) for path in paths):
                    service._mark_changed()

        observer = Observer()
        observer.schedule(Handler(), str(self.options.input_root), recursive=True)
        observer.start()
        return observer

    def _poll_once(self) -> None:
        current = self._snapshot()
        if current != self._known_signatures:
            self._known_signatures = current
            self._mark_changed()

    def _snapshot(self) -> dict[Path, tuple[int, int]]:
        signatures: dict[Path, tuple[int, int]] = {}
        for path in self._iter_candidate_files():
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            signatures[path] = (stat.st_size, stat.st_mtime_ns)
        return signatures

    def _iter_candidate_files(self) -> Iterable[Path]:
        for pattern in self.options.patterns:
            yield from self.options.input_root.rglob(pattern)

    def _matches(self, path: Path) -> bool:
        name = path.name
        return any(fnmatch.fnmatch(name, pattern) for pattern in self.options.patterns)

    def _mark_changed(self) -> None:
        self._changed_event.set()

    def _debounce(self) -> None:
        deadline = time.monotonic() + self.options.debounce_seconds
        while not self._stop_event.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            if self._changed_event.wait(min(remaining, 1.0)):
                self._changed_event.clear()
                deadline = time.monotonic() + self.options.debounce_seconds

    def _wait_for_stable_files(self) -> None:
        stable_since: float | None = None
        previous = self._snapshot()

        while not self._stop_event.is_set():
            time.sleep(self.options.poll_interval_seconds)
            current = self._snapshot()
            if current == previous:
                if stable_since is None:
                    stable_since = time.monotonic()
                if time.monotonic() - stable_since >= self.options.stable_seconds:
                    self._known_signatures = current
                    return
            else:
                previous = current
                stable_since = None

    def _start_job_when_idle(self) -> None:
        while not self._stop_event.is_set():
            status = get_subset_job_status()
            if status.get("status") not in {"queued", "running"}:
                break
            print(
                f"[subset-watch] subset job already {status.get('status')}; waiting",
                flush=True,
            )
            self._stop_event.wait(self.options.poll_interval_seconds)

        if self._stop_event.is_set():
            return

        status, started = start_subset_job()
        if started:
            print(f"[subset-watch] started subset job: {status.get('job_id')}", flush=True)
        else:
            print(f"[subset-watch] subset job not started: {status.get('status')}", flush=True)


def main(argv: list[str] | None = None) -> None:
    settings = get_settings()
    watch_settings = settings.subset_watch

    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", default=str(settings.paths.subset_input_root))
    parser.add_argument("--debounce-seconds", type=float, default=watch_settings.debounce_seconds)
    parser.add_argument("--stable-seconds", type=float, default=watch_settings.stable_seconds)
    parser.add_argument("--poll-interval", type=float, default=watch_settings.poll_interval_seconds)
    parser.add_argument("--pattern", action="append", dest="patterns")
    args = parser.parse_args(argv)

    if not watch_settings.enabled:
        print("[subset-watch] disabled by config subset_watch.enabled=false", flush=True)
        return

    patterns = tuple(args.patterns) if args.patterns else watch_settings.patterns
    service = SubsetWatchService(
        WatchOptions(
            input_root=Path(args.input_root).expanduser().resolve(),
            debounce_seconds=max(args.debounce_seconds, 0),
            stable_seconds=max(args.stable_seconds, 0),
            poll_interval_seconds=max(args.poll_interval, 1),
            patterns=patterns,
        )
    )

    def stop(_signum, _frame) -> None:
        print("[subset-watch] stopping", flush=True)
        service.stop()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    service.run()
