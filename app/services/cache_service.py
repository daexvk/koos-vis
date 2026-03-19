from pathlib import Path
import json

CACHE_ROOT = Path.home() / "data" / "z6_sample"

def read_tile(z: int, x: int, y: int):
    tile_path = CACHE_ROOT / str(z) / str(x) / f"{y}.json"

    if not tile_path.exists():
        return None

    with open(tile_path, "r", encoding="utf-8") as f:
        return json.load(f)