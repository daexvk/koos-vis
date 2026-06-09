from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "koos-back.json"
CONFIG_ENV_NAME = "KOOS_BACK_CONFIG"


@dataclass(frozen=True)
class ServerSettings:
    host: str
    port: int
    workers: int


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


@dataclass(frozen=True)
class Settings:
    config_path: Path | None
    server: ServerSettings
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
    paths_config = _section(config, "paths")

    server = ServerSettings(
        host=str(server_config.get("host", "127.0.0.1")),
        port=int(server_config.get("port", 8197)),
        workers=int(server_config.get("workers", 1)),
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
    )
    return Settings(config_path=config_path, server=server, paths=paths)


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
