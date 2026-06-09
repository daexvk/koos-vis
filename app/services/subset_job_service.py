from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from uuid import uuid4

from app.core.config import CONFIG_ENV_NAME, get_settings
from app.services.cache_service import SUBSET_INPUT_ROOT, SUBSET_ROOT


SETTINGS = get_settings()

# Runtime status/lock files for subset jobs. This is configurable because the
# packaged Electron app may need a writable location outside the binary folder.
JOB_ROOT = SETTINGS.paths.subset_job_root
STATUS_PATH = JOB_ROOT / "status.json"
LOCK_PATH = JOB_ROOT / "run.lock"


def get_subset_job_status() -> dict:
    state = _read_state()
    if state["status"] in {"queued", "running"} and not _pid_alive(state.get("pid")):
        state["status"] = "failed"
        state["error"] = state.get("error") or "subset process is not running"
        state["finished_at"] = state.get("finished_at") or _utc_now().isoformat()
        state["pid"] = None
        _write_state(state)
        _clear_lock()
    return state


def start_subset_job() -> tuple[dict, bool]:
    JOB_ROOT.mkdir(parents=True, exist_ok=True)

    current = get_subset_job_status()
    if current["status"] in {"queued", "running"}:
        return current, False
    _clear_lock()

    job_id = f"subset-{_utc_now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    state = _initial_state(job_id)
    _write_state(state)

    try:
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        current = get_subset_job_status()
        return current, False

    try:
        proc = subprocess.Popen(
            [
                *_backend_command(),
                *(_config_args()),
                "subset-worker",
                "--job-id",
                job_id,
                "--input-root",
                str(SUBSET_INPUT_ROOT),
                "--output-root",
                str(SUBSET_ROOT),
                "--status-path",
                str(STATUS_PATH),
                "--lock-path",
                str(LOCK_PATH),
            ],
            cwd=Path(__file__).resolve().parents[2],
            start_new_session=True,
        )
        os.write(fd, str(proc.pid).encode("ascii"))
    finally:
        os.close(fd)

    state["status"] = "running"
    state["pid"] = proc.pid
    _write_state(state)
    return state, True


def stop_subset_job() -> dict:
    state = get_subset_job_status()
    pid = state.get("pid")
    if state["status"] in {"queued", "running"} and _pid_alive(pid):
        try:
            os.killpg(int(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError as exc:
            state["error"] = f"permission denied stopping subset process: {exc}"
            _write_state(state)
            return state

    state["status"] = "canceled"
    state["pid"] = None
    state["finished_at"] = _utc_now().isoformat()
    state["error"] = None
    _write_state(state)
    _clear_lock()
    return state


def _initial_state(job_id: str | None = None) -> dict:
    return {
        "job_id": job_id,
        "status": "idle" if job_id is None else "queued",
        "pid": None,
        "input_root": str(SUBSET_INPUT_ROOT),
        "output_root": str(SUBSET_ROOT),
        "total_files": 0,
        "completed_files": 0,
        "current_file": None,
        "error": None,
        "started_at": _utc_now().isoformat() if job_id is not None else None,
        "finished_at": None,
    }


def _read_state() -> dict:
    if not STATUS_PATH.exists():
        return _initial_state()
    try:
        with open(STATUS_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
    except json.JSONDecodeError:
        return _initial_state()

    base = _initial_state()
    base.update(state)
    return base


def _write_state(state: dict) -> None:
    JOB_ROOT.mkdir(parents=True, exist_ok=True)
    tmp_path = STATUS_PATH.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    tmp_path.replace(STATUS_PATH)


def _clear_lock() -> None:
    try:
        LOCK_PATH.unlink()
    except FileNotFoundError:
        pass


def _pid_alive(pid) -> bool:
    if pid is None:
        return False

    pid = int(pid)

    try:
        waited_pid, _status = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        waited_pid = 0
    except OSError:
        waited_pid = 0
    if waited_pid == pid:
        return False

    try:
        stat = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "stat="],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.SubprocessError, OSError):
        stat = ""
    if stat.startswith("Z"):
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _config_args() -> list[str]:
    config_path = os.getenv(CONFIG_ENV_NAME)
    if not config_path:
        config_path = str(SETTINGS.config_path) if SETTINGS.config_path is not None else None
    return ["--config", config_path] if config_path else []


def _backend_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "app.cli"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
