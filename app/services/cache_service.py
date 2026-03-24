from pathlib import Path
import json

CACHE_ROOT = Path.home() / "data" / "tiles"

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