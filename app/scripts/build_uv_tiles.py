from __future__ import annotations

import argparse
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


def parse_time_indices(value: str) -> list[int]:
    if not value:
        raise ValueError("time index list cannot be empty")
    if value.strip().lower() == "all":
        return []

    indices: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if end < start:
                raise ValueError(f"invalid time range: {part}")
            indices.extend(range(start, end + 1))
        else:
            indices.append(int(part))

    return sorted(set(indices))


def write_times_meta(
    output_root: Path,
    ds_time_values,
    source_file: str,
    time_indices: list[int],
) -> None:
    payload = {
        "source_file": source_file,
        "time_indices": time_indices,
        "times": [
            {
                "time_index": int(i),
                "time_value": str(ds_time_values[i]),
            }
            for i in time_indices
        ],
    }
    with open(output_root / "times.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def process_zoom_level(
    lon: np.ndarray,
    lat: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    simplices: np.ndarray,
    zoom: int,
    cache_root: Path,
    time_index: int,
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
            "time_index": time_index,
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
    time_index: int,
    point_count: int,
    triangle_count: int,
    tile_count: int,
) -> None:
    meta = {
        "source_file": source_file,
        "zoom": zoom,
        "time_index": time_index,
        "time_value": str(ds_time_values[time_index]),
        "point_count": point_count,
        "triangle_count": triangle_count,
        "tile_count": tile_count,
        "fields": ["idx", "lat", "lon", "u", "v"],
    }
    with open(z_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def build_uv_tiles(
    slf_path: Path,
    output_root: Path,
    min_z: int = MIN_ZOOM,
    max_z: int = MAX_ZOOM,
    time_indices: list[int] | None = None,
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    if time_indices is None:
        time_indices = [TIME_INDEX]

    ds = xr.open_dataset(slf_path, engine="selafin")
    ds_time_values = ds.coords["time"].values
    max_time_index = len(ds_time_values) - 1
    if time_indices == []:
        time_indices = list(range(max_time_index + 1))
    invalid = [i for i in time_indices if i < 0 or i > max_time_index]
    if invalid:
        raise ValueError(
            f"time index out of range: {invalid}. valid range=0-{max_time_index}"
        )

    lon = ds.coords["x"].values
    lat = ds.coords["y"].values

    ikle2 = np.array(ds.attrs["ikle2"])
    if ikle2.min() >= 1:
        ikle2 -= 1

    write_times_meta(output_root, ds_time_values, str(slf_path), time_indices)

    for time_index in time_indices:
        print(f"[time {time_index}] build UV tiles")
        ds_t = ds.isel(time=time_index)
        u = ds_t["U"].values
        v = ds_t["V"].values
        time_root = output_root / f"t{time_index}"

        for zoom in range(min_z, max_z + 1):
            n_pts, n_tri, n_tiles = process_zoom_level(
                lon, lat, u, v, ikle2, zoom, time_root, time_index,
            )
            save_meta(time_root / str(zoom), ds_time_values,
                      str(slf_path), zoom, time_index, n_pts, n_tri, n_tiles)

    ds.close()

    print("preprocess complete")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slf", default=str(DATA_FILE), help="Input SLF path")
    parser.add_argument(
        "--output",
        default=str(CACHE_ROOT),
        help="Output root for UV tiles",
    )
    parser.add_argument("--min-z", type=int, default=MIN_ZOOM)
    parser.add_argument("--max-z", type=int, default=MAX_ZOOM)
    parser.add_argument("--time-index", type=int, default=TIME_INDEX)
    parser.add_argument(
        "--time-indices",
        default=None,
        help="Comma-separated time indices or inclusive ranges, e.g. 0,1,2 or 0-24",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_uv_tiles(
        slf_path=Path(args.slf).expanduser().resolve(),
        output_root=Path(args.output).expanduser().resolve(),
        min_z=args.min_z,
        max_z=args.max_z,
        time_indices=(
            parse_time_indices(args.time_indices)
            if args.time_indices is not None
            else [args.time_index]
        ),
    )


if __name__ == "__main__":
    main()
