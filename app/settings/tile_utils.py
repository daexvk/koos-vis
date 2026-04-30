from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np


def lonlat_to_xyz_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    lat = max(min(lat, 85.05112878), -85.05112878)

    n = 2 ** z
    xtile = int((lon + 180.0) / 360.0 * n)

    lat_rad = math.radians(lat)
    ytile = int(
        (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi)
        / 2.0
        * n
    )

    xtile = max(0, min(xtile, n - 1))
    ytile = max(0, min(ytile, n - 1))
    return xtile, ytile


def tiles_around(cx: int, cy: int) -> set[tuple[int, int]]:
    return {(cx + dx, cy + dy) for dx in range(-2, 3) for dy in range(-2, 3)}


def collect_target_tiles(locations: dict[str, tuple[int, int, int]]) -> set[tuple[int, int]]:
    tiles: set[tuple[int, int]] = set()
    for _, cx, cy in locations.values():
        tiles |= tiles_around(cx, cy)
    return tiles


def bucket_nodes(
    lon: np.ndarray,
    lat: np.ndarray,
    h: np.ndarray,
    z: int,
    target_tiles: set[tuple[int, int]] | None = None,
    indices: np.ndarray | None = None,
) -> dict[tuple[int, int], list[dict]]:
    """노드를 타일별로 분류한다. 각 포인트에 idx를 부여.

    indices가 주어지면 원본 인덱스를 idx로 사용한다.
    """
    buckets: dict[tuple[int, int], list[dict]] = defaultdict(list)

    for i in range(len(lon)):
        tx, ty = lonlat_to_xyz_tile(float(lon[i]), float(lat[i]), z)
        if target_tiles is not None and (tx, ty) not in target_tiles:
            continue
        idx = int(indices[i]) if indices is not None else int(i)
        buckets[(tx, ty)].append({
            "idx": idx,
            "lat": float(lat[i]),
            "lon": float(lon[i]),
            "h": float(h[i]),
        })

    return buckets


def save_tiles(
    z_dir: Path,
    z: int,
    buckets: dict[tuple[int, int], list[dict]],
    simplices: np.ndarray,
) -> None:
    """connectivity + 타일별 포인트 JSON을 저장한다."""
    z_dir.mkdir(parents=True, exist_ok=True)

    with open(z_dir / "connectivity.json", "w", encoding="utf-8") as f:
        json.dump({"triangles": simplices.tolist()}, f, ensure_ascii=False)

    for (tile_x, tile_y), points in buckets.items():
        x_dir = z_dir / str(tile_x)
        x_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "z": z, "x": tile_x, "y": tile_y,
            "time_index": 0, "points": points,
        }
        with open(x_dir / f"{tile_y}.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)


def save_meta(
    cache_root: Path,
    ds_time_values,
    source_file: str,
    zoom: int,
    coarsen_factor: float,
    point_count: int,
    triangle_count: int,
    tile_count: int,
) -> None:
    meta = {
        "source_file": source_file,
        "zoom": zoom,
        "coarsen_factor": coarsen_factor,
        "time_index": 0,
        "time_value": str(ds_time_values[0]),
        "point_count": point_count,
        "triangle_count": triangle_count,
        "tile_count": tile_count,
        "fields": ["idx", "lat", "lon", "h"],
    }
    with open(cache_root / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
