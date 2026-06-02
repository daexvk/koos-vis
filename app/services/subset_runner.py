from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.subset_engine.subset import collect_files, start_subset


ProgressCallback = Callable[[str, Path | None, int, int], None]


def run_auto_subset(
    input_root: Path,
    output_root: Path,
    progress: ProgressCallback | None = None,
) -> int:
    if not input_root.exists():
        raise FileNotFoundError(f"subset input root not found: {input_root}")
    if not input_root.is_dir():
        raise NotADirectoryError(f"subset input root is not a directory: {input_root}")

    if progress is not None:
        progress("running", None, 0, 0)

    files = collect_files(input_root)
    total = len(files)
    if progress is not None:
        progress("running", None, 0, total)

    completed = 0
    def on_file_start(path: Path) -> None:
        if progress is not None:
            progress("running", path, completed, total)

    for completed_file in start_subset(
        files,
        output_root,
        file_callback=on_file_start,
    ):
        completed += 1
        if progress is not None:
            progress("running", Path(completed_file), completed, total)

    return total
