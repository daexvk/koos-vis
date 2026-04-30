from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import xarray as xr

from app.settings.tile_utils import lonlat_to_xyz_tile


DATA_FILE = Path.home() / "data" / "0314_surge_res_korea.slf"
CACHE_ROOT = DATA_FILE.parent / "tiles_uv"

MIN_ZOOM = 6
MAX_ZOOM = 10
TIME_INDEX = 864


def process_zoom_level(
    lon: np.ndarray,
    lat: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    simplices: np.ndarray,
    zoom: int,
    cache_root: Path,
) -> tuple[int, int, int]:
    """특정 줌 레벨에 대해 타일 저장을 수행한다 (u, v)."""
    buckets: dict[tuple[int, int], list[dict]] = defaultdict(list)
    point_tile = np.empty((len(lon), 2), dtype=np.int64)
    for i in range(len(lon)):
        tx, ty = lonlat_to_xyz_tile(float(lon[i]), float(lat[i]), zoom)
        point_tile[i, 0] = tx
        point_tile[i, 1] = ty
        buckets[(tx, ty)].append({
            "idx": int(i),
            "lat": float(lat[i]),
            "lon": float(lon[i]),
            "u": float(u[i]),
            "v": float(v[i]),
        })

    # 삼각형의 꼭짓점 중 하나라도 속한 타일에 그 삼각형을 포함시킨다.
    # 타일 밖 정점 idx는 그대로 유지하여 경계에서 메시가 끊기지 않게 한다.
    tri_buckets: dict[tuple[int, int], list[list[int]]] = defaultdict(list)
    for tri in simplices:
        tri_list = [int(v) for v in tri]
        tiles = {(int(point_tile[v, 0]), int(point_tile[v, 1])) for v in tri}
        for t in tiles:
            tri_buckets[t].append(tri_list)

    z_dir = cache_root / str(zoom)
    z_dir.mkdir(parents=True, exist_ok=True)

    with open(z_dir / "connectivity.json", "w", encoding="utf-8") as f:
        json.dump({"triangles": simplices.tolist()}, f, ensure_ascii=False)

    for (tile_x, tile_y), points in buckets.items():
        x_dir = z_dir / str(tile_x)
        x_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "z": zoom, "x": tile_x, "y": tile_y,
            "time_index": TIME_INDEX,
            "points": points,
            "triangles": tri_buckets.get((tile_x, tile_y), []),
        }
        with open(x_dir / f"{tile_y}.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)

    n_nodes = len(lon)
    print(f"z{zoom}: {len(simplices)} tri, {n_nodes} nodes, {len(buckets)} tiles")

    return n_nodes, len(simplices), len(buckets)


def save_meta(
    z_dir: Path,
    ds_time_values,
    source_file: str,
    zoom: int,
    point_count: int,
    triangle_count: int,
    tile_count: int,
) -> None:
    meta = {
        "source_file": source_file,
        "zoom": zoom,
        "time_index": TIME_INDEX,
        "time_value": str(ds_time_values[TIME_INDEX]),
        "point_count": point_count,
        "triangle_count": triangle_count,
        "tile_count": tile_count,
        "fields": ["idx", "lat", "lon", "u", "v"],
    }
    with open(z_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def main() -> None:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)

    ds = xr.open_dataset(DATA_FILE, engine="selafin")
    ds_t = ds.isel(time=TIME_INDEX)
    lon = ds_t.coords["x"].values
    lat = ds_t.coords["y"].values
    u = ds_t["U"].values
    v = ds_t["V"].values

    ikle2 = np.array(ds.attrs["ikle2"])
    if ikle2.min() >= 1:
        ikle2 -= 1

    for zoom in range(MIN_ZOOM, MAX_ZOOM + 1):
        n_pts, n_tri, n_tiles = process_zoom_level(
            lon, lat, u, v, ikle2, zoom, CACHE_ROOT,
        )
        save_meta(CACHE_ROOT / str(zoom), ds.coords["time"].values,
                  str(DATA_FILE), zoom, n_pts, n_tri, n_tiles)

    print("preprocess complete")


if __name__ == "__main__":
    main()
