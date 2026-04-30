from __future__ import annotations

from pathlib import Path
import json

CACHE_ROOT = Path.home() / "data" / "tiles"
DATA_ROOT = Path.home() / "data"
COASTLINE_TILE_ROOT = Path.home() / "data" / "coastline_tiles"
WEBP_ROOT = Path.home() / "data" / "webp"
FLOOD_ROOT = Path.home() / "data" / "flood_tiles"
UV_ROOT = Path.home() / "data" / "tiles_uv"
FLOOD_TIME_ROOT = Path.home() / "data" / "flood_tiles_time"
UV_TIME_ROOT = Path.home() / "data" / "tiles_uv_time"

def get_coastline_path():
    return DATA_ROOT / "coastline.json"
    # return None

def get_coastline_simplified_path(z: int):
    COASTLINE_SIMPLIFIED_ROOT = Path.home() / "data" / "coastline"
    COASTLINE_SIMPLIFIED_ZOOMS = (6, 8, 10, 12)
    if z not in COASTLINE_SIMPLIFIED_ZOOMS:
        return None

    path = COASTLINE_SIMPLIFIED_ROOT / str(z) / "coastline.geojson"

    if not path.exists():
        return None

    return path


def get_coastline_tile_path(z: int, x: int, y: int):
    path = COASTLINE_TILE_ROOT / str(z) / str(x) / f"{y}.geojson"

    if not path.exists():
        return None

    return path

def get_webp_tile_path(z: int, x: int, y: int):
    path = WEBP_ROOT / str(z) / str(x) / f"{y}.webp"

    if not path.exists():
        return None

    return path

def read_tile(z: int, x: int, y: int):
    tile_path = CACHE_ROOT / str(z) / str(x) / f"{y}.json"

    if not tile_path.exists():
        return None

    with open(tile_path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_connectivity(z: int):
    conn_path = CACHE_ROOT / str(z) / "connectivity.json"

    if not conn_path.exists():
        return None

    with open(conn_path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_times(root: Path):
    path = root / "times.json"

    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_time_tile_path(
    root: Path,
    time_index: int,
    z: int,
    x: int,
    y: int,
    legacy_time_index: int | None = None,
):
    path = root / f"t{time_index}" / str(z) / str(x) / f"{y}.json"

    if path.exists():
        return path

    # Backward compatibility for older one-time caches.
    if legacy_time_index is not None and time_index == legacy_time_index:
        legacy_path = root / str(z) / str(x) / f"{y}.json"
        if legacy_path.exists():
            return legacy_path

    return None


def get_time_connectivity_path(
    root: Path,
    time_index: int,
    z: int,
    legacy_time_index: int | None = None,
):
    path = root / f"t{time_index}" / str(z) / "connectivity.json"

    if path.exists():
        return path

    # Backward compatibility for older one-time caches.
    if legacy_time_index is not None and time_index == legacy_time_index:
        legacy_path = root / str(z) / "connectivity.json"
        if legacy_path.exists():
            return legacy_path

    return None


def read_uv_times():
    return read_times(UV_TIME_ROOT)


def read_flood_times():
    return read_times(FLOOD_TIME_ROOT)


def get_flood_tile_path(time_index: int, z: int, x: int, y: int):
    path = get_time_tile_path(FLOOD_TIME_ROOT, time_index, z, x, y)

    if path is None and time_index == 0:
        path = FLOOD_ROOT / str(z) / str(x) / f"{y}.json"
        if not path.exists():
            path = None

    if path is None:
        return None

    return path


def get_flood_connectivity_path(time_index: int, z: int):
    path = get_time_connectivity_path(FLOOD_TIME_ROOT, time_index, z)

    if path is None and time_index == 0:
        path = FLOOD_ROOT / str(z) / "connectivity.json"
        if not path.exists():
            path = None

    if path is None:
        return None

    return path


def get_uv_tile_path(time_index: int, z: int, x: int, y: int):
    path = get_time_tile_path(UV_TIME_ROOT, time_index, z, x, y)

    if path is None and time_index == 864:
        path = UV_ROOT / str(z) / str(x) / f"{y}.json"
        if not path.exists():
            path = None

    if path is None:
        return None

    return path


def get_uv_connectivity_path(time_index: int, z: int):
    path = get_time_connectivity_path(UV_TIME_ROOT, time_index, z)

    if path is None and time_index == 864:
        path = UV_ROOT / str(z) / "connectivity.json"
        if not path.exists():
            path = None

    if path is None:
        return None

    return path
