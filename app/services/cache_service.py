from pathlib import Path
import json

CACHE_ROOT = Path.home() / "data" / "tiles"
DATA_ROOT = Path.home() / "data"
COASTLINE_ROOT = Path.home() / "data" / "coastline_tiles_topo"
WEBP_ROOT = Path.home() / "data" / "webp"

def get_coastline_path():
    # return DATA_ROOT / "coastline.json"
    return None

def get_coastline_topo_path(z: int, x: int, y: int):
    path = COASTLINE_ROOT / str(z) / str(x) / f"{y}.topojson"

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