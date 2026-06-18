from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import os
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else PROJECT_ROOT
DEFAULT_CONFIG_PATH = RUNTIME_ROOT / "config" / "koos-back.json"
CONFIG_ENV_NAME = "KOOS_BACK_CONFIG"


@dataclass(frozen=True)
class ServerSettings:
    host: str
    port: int
    workers: int
    open_browser: bool
    browser_url: str | None


@dataclass(frozen=True)
class AuthSettings:
    api_key: str | None


@dataclass(frozen=True)
class SubsetWatchSettings:
    enabled: bool
    debounce_seconds: float
    stable_seconds: float
    poll_interval_seconds: float
    patterns: tuple[str, ...]


@dataclass(frozen=True)
class PathSettings:
    # T7 같은 외부 원본 데이터 루트. DOUT/POST/TRACK 입력은 이 기준으로 해석한다.
    input_root: Path
    # 프로젝트 내부 생성물 루트. subset/tile/boundary 출력은 이 기준으로 해석한다.
    output_root: Path
    subset_input_root: Path
    timeseries_root: Path
    subset_track_root: Path
    subset_output_root: Path
    boundary_root: Path
    subset_job_root: Path
    tile_root: Path
    coastline_root: Path
    coastline_tile_root: Path
    webp_root: Path
    flood_root: Path
    uv_root: Path
    wave_root: Path
    flood_time_root: Path
    uv_time_root: Path
    wave_time_root: Path
    coastline_json: Path
    static_root: Path


@dataclass(frozen=True)
class Settings:
    config_path: Path | None
    server: ServerSettings
    auth: AuthSettings
    subset_watch: SubsetWatchSettings
    paths: PathSettings


def set_config_path(config_path: str | Path | None) -> None:
    if config_path is None:
        return
    os.environ[CONFIG_ENV_NAME] = str(Path(config_path).expanduser().resolve())
    get_settings.cache_clear()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    config_path = _find_config_path()
    config = _load_json(config_path) if config_path is not None else {}
    config_dir = config_path.parent if config_path is not None else PROJECT_ROOT

    server_config = _section(config, "server")
    auth_config = _section(config, "auth")
    subset_watch_config = _section(config, "subset_watch")
    paths_config = _section(config, "paths")

    server = ServerSettings(
        host=str(server_config.get("host", "127.0.0.1")),
        port=int(server_config.get("port", 8197)),
        workers=int(server_config.get("workers", 1)),
        open_browser=_as_bool(server_config.get("open_browser", False)),
        browser_url=_optional_str(server_config.get("browser_url")),
    )
    auth = AuthSettings(
        api_key=_optional_str(auth_config.get("api_key")) or _optional_str(os.getenv("API_KEY")),
    )
    subset_watch = SubsetWatchSettings(
        enabled=_as_bool(subset_watch_config.get("enabled", False)),
        debounce_seconds=float(subset_watch_config.get("debounce_seconds", 30)),
        stable_seconds=float(subset_watch_config.get("stable_seconds", 60)),
        poll_interval_seconds=float(subset_watch_config.get("poll_interval_seconds", 5)),
        patterns=tuple(
            str(pattern)
            for pattern in subset_watch_config.get(
                "patterns",
                ["*_surge_*.slf", "*_wave_*.slf"],
            )
        ),
    )

    input_root = _resolve_root(
        paths_config.get("input_root"),
        default=Path(os.getenv("INPUT_ROOT", "/Volumes/T7/sample/NSTORM")),
        config_dir=config_dir,
    )
    output_root = _resolve_root(
        paths_config.get("output_root"),
        default=Path(os.getenv("DATA_ROOT", PROJECT_ROOT / "data")),
        config_dir=config_dir,
    )

    paths = PathSettings(
        input_root=input_root,
        output_root=output_root,
        subset_input_root=_resolve_under_root(
            paths_config.get("subset_input_root"),
            default=os.getenv("SUBSET_INPUT_ROOT", "DOUT"),
            root=input_root,
        ),
        timeseries_root=_resolve_under_root(
            paths_config.get("timeseries_root"),
            default=os.getenv("TIMESERIES_ROOT", "POST"),
            root=input_root,
        ),
        subset_track_root=_resolve_under_root(
            paths_config.get("subset_track_root"),
            default=os.getenv("SUBSET_TRACK_ROOT", "DAIN/TRACK"),
            root=input_root,
        ),
        subset_output_root=_resolve_under_root(
            paths_config.get("subset_output_root"),
            default=os.getenv("SUBSET_ROOT", "subset"),
            root=output_root,
        ),
        boundary_root=_resolve_under_root(
            paths_config.get("boundary_root"),
            default=os.getenv("BOUNDARY_ROOT", "boundaries"),
            root=output_root,
        ),
        subset_job_root=_resolve_under_root(
            paths_config.get("subset_job_root"),
            default=os.getenv("SUBSET_JOB_ROOT", "runtime/subset_jobs"),
            root=output_root,
        ),
        tile_root=_resolve_under_root(paths_config.get("tile_root"), "tiles", output_root),
        coastline_root=_resolve_under_root(paths_config.get("coastline_root"), "coastline", output_root),
        coastline_tile_root=_resolve_under_root(
            paths_config.get("coastline_tile_root"),
            "coastline_tiles",
            output_root,
        ),
        webp_root=_resolve_under_root(paths_config.get("webp_root"), "webp", output_root),
        flood_root=_resolve_under_root(paths_config.get("flood_root"), "flood_tiles", output_root),
        uv_root=_resolve_under_root(paths_config.get("uv_root"), "tiles_uv", output_root),
        wave_root=_resolve_under_root(paths_config.get("wave_root"), "wave_tiles", output_root),
        flood_time_root=_resolve_under_root(
            paths_config.get("flood_time_root"),
            "flood_tiles_time",
            output_root,
        ),
        uv_time_root=_resolve_under_root(paths_config.get("uv_time_root"), "tiles_uv_time", output_root),
        wave_time_root=_resolve_under_root(
            paths_config.get("wave_time_root"),
            "wave_tiles_time",
            output_root,
        ),
        coastline_json=_resolve_under_root(paths_config.get("coastline_json"), "coastline.json", output_root),
        static_root=_resolve_root(
            paths_config.get("static_root"),
            default=RUNTIME_ROOT / "static",
            config_dir=config_dir,
        ),
    )
    return Settings(
        config_path=config_path,
        server=server,
        auth=auth,
        subset_watch=subset_watch,
        paths=paths,
    )


def _find_config_path() -> Path | None:
    env_path = os.getenv(CONFIG_ENV_NAME)
    if env_path:
        return Path(env_path).expanduser().resolve()
    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH.resolve()
    return None


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"config root must be an object: {path}")
    return data


def _section(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"config section must be an object: {name}")
    return value


def _resolve_root(value: Any, default: Path, config_dir: Path) -> Path:
    path = Path(str(value)) if value is not None else default
    path = path.expanduser()
    if path.is_absolute():
        return path
    return (config_dir / path).resolve()


def _resolve_under_root(value: Any, default: str, root: Path) -> Path:
    path = Path(str(value if value is not None else default)).expanduser()
    if path.is_absolute():
        return path
    return (root / path).resolve()


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
