import multiprocessing as mp
import threading
from contextlib import contextmanager
from typing import Optional

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


# 워커 프로세스에서 init_worker가 채워주는 큐 핸들. 메인은 None.
_queue = None


def init_worker(queue) -> None:
    """Pool initializer. 각 워커가 같은 Manager Queue를 모듈 전역으로 보유하게 만듦."""
    global _queue
    _queue = queue


def start_file_progress(queue, key: str, total: int, desc: str) -> None:
    """메인 프로세스에서 파일 단위 progress bar를 시작."""
    if queue is not None:
        queue.put(("start", key, total, desc))


def end_file_progress(queue, key: str) -> None:
    """메인 프로세스에서 파일 단위 progress bar를 종료."""
    if queue is not None:
        queue.put(("done", key))


def advance_file_progress(key: str, n: int = 1) -> None:
    """워커 프로세스에서 메인의 파일 bar를 advance. 큐가 없으면 no-op."""
    q = _queue
    if q is not None:
        q.put(("advance", key, n))


@contextmanager
def track_iteration(key: str, total: int, desc: str):
    """워커 안에서 한 작업의 진행을 메인으로 push. 큐가 없으면 no-op."""
    q = _queue
    if q is None:
        yield lambda n=1: None
        return
    q.put(("start", key, total, desc))
    try:
        def advance(n: int = 1):
            q.put(("advance", key, n))
        yield advance
    finally:
        q.put(("done", key))


def _make_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
    )


class ProgressSession:
    """메인에서 rich.Progress를 띄우고, 워커가 보낸 이벤트를 백그라운드 스레드로 소비.

    워커가 send_iteration를 호출하면 한 줄짜리 bar가 즉시 생기고, done 시점에 사라짐.
    파일 전체 진행은 advance_file()로 직접 갱신.
    """

    def __init__(self, total_files: int):
        self._total_files = total_files
        self._manager: Optional[mp.managers.SyncManager] = None
        self.queue = None
        self._progress: Optional[Progress] = None
        self._file_task = None
        self._tasks: dict[str, int] = {}
        self._stop = threading.Event()
        self._drainer: Optional[threading.Thread] = None

    def __enter__(self):
        self._manager = mp.Manager()
        self._manager.__enter__()
        self.queue = self._manager.Queue()

        self._progress = _make_progress()
        self._progress.__enter__()
        self._file_task = self._progress.add_task("files", total=self._total_files)

        self._drainer = threading.Thread(target=self._drain, daemon=True)
        self._drainer.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop.set()
        if self._drainer is not None:
            self._drainer.join(timeout=2)
        self._progress.__exit__(exc_type, exc_val, exc_tb)
        self._manager.__exit__(exc_type, exc_val, exc_tb)

    def _drain(self) -> None:
        while not self._stop.is_set():
            try:
                event = self.queue.get(timeout=0.05)
            except Exception:
                continue
            self._handle(event)

    def _handle(self, event) -> None:
        kind, *rest = event
        if kind == "start":
            key, total, desc = rest
            self._tasks[key] = self._progress.add_task(desc, total=total)
        elif kind == "advance":
            key, n = rest
            tid = self._tasks.get(key)
            if tid is not None:
                self._progress.advance(tid, n)
        elif kind == "done":
            (key,) = rest
            tid = self._tasks.pop(key, None)
            if tid is not None:
                self._progress.remove_task(tid)

    def advance_file(self) -> None:
        self._progress.advance(self._file_task)
