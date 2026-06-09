from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import traceback

from app.services.subset_runner import run_auto_subset


def main(argv: list[str] | None = None) -> None:
    os.umask(0o022)

    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--status-path", required=True)
    parser.add_argument("--lock-path", required=True)
    args = parser.parse_args(argv)

    status_path = Path(args.status_path)
    lock_path = Path(args.lock_path)
    input_root = Path(args.input_root)
    output_root = Path(args.output_root)

    def update(**changes) -> None:
        state = _read_state(status_path)
        state.update(changes)
        _write_state(status_path, state)

    def progress(status, current_file, completed_files, total_files) -> None:
        update(
            status=status,
            current_file=current_file.name if current_file is not None else None,
            completed_files=completed_files,
            total_files=total_files,
        )

    update(
        job_id=args.job_id,
        status="running",
        input_root=str(input_root),
        output_root=str(output_root),
        error=None,
        started_at=_utc_now().isoformat(),
        finished_at=None,
    )

    try:
        total = run_auto_subset(input_root, output_root, progress=progress)
    except Exception as exc:
        update(
            status="failed",
            error=f"{exc}\n{traceback.format_exc()}",
            finished_at=_utc_now().isoformat(),
        )
        _clear_lock(lock_path)
        raise

    update(
        status="succeeded",
        current_file=None,
        completed_files=total,
        total_files=total,
        error=None,
        finished_at=_utc_now().isoformat(),
    )
    _clear_lock(lock_path)


def _read_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def _write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


def _clear_lock(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


if __name__ == "__main__":
    main()
