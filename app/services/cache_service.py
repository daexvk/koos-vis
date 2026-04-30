from pathlib import Path
import json

CACHE_ROOT = Path.home() / "data" / "tiles"
DATA_ROOT = Path.home() / "data"
COASTLINE_TILE_ROOT = Path.home() / "data" / "coastline_tiles"
WEBP_ROOT = Path.home() / "data" / "webp"
FLOOD_ROOT = Path.home() / "data" / "flood_tiles"
UV_ROOT = Path.home() / "data" / "tiles_uv"

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
    
def get_flood_tile_path(z: int, x: int, y: int):
    path = FLOOD_ROOT / str(z) / str(x) / f"{y}.json"

    if not path.exists():
        return None

    return path


def get_flood_connectivity_path(z: int):
    path = FLOOD_ROOT / str(z) / "connectivity.json"

    if not path.exists():
        return None

    return path


def get_uv_tile_path(z: int, x: int, y: int):
    path = UV_ROOT / str(z) / str(x) / f"{y}.json"

    if not path.exists():
        return None

    return path


def get_uv_connectivity_path(z: int):
    path = UV_ROOT / str(z) / "connectivity.json"

    if not path.exists():
        return None

    return path