from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import xarray as xr

from app.settings.mesh_utils import subset_connectivity
from app.settings.tile_utils import collect_target_tiles, lonlat_to_xyz_tile


SLF_PATH = (
    Path("/Volumes/T7/sample")
    / "NSTORM"
    / "DOUT"
    / "WAVE"
    / "KOREA"
    / "0314_01_wave_res_korea.slf"
)
OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "data" / "wave_tiles"


Z11_SUBSET_TILES = {
    "jinhae": (11, 1756, 810),
    "busan": (11, 1758, 810),
    "donghae": (11, 1758, 793),
    "gangjeong": (11, 1743, 823),
    "mokpo": (11, 1743, 812),
}


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


def find_data_var(ds: xr.Dataset, candidates: list[str]) -> str:
    normalized = {
        " ".join(name.lower().split()): name
        for name in ds.data_vars
    }
    for candidate in candidates:
        key = " ".join(candidate.lower().split())
        if key in normalized:
            return normalized[key]

    for candidate in candidates:
        key = candidate.lower()
        for name in ds.data_vars:
            if key in name.lower():
                return name

    raise ValueError(
        f"variable not found. candidates={candidates}, available={list(ds.data_vars)}"
    )


def to_numpy_1d(da: xr.DataArray, time_index: int | None = None) -> np.ndarray:
    arr = da
    if time_index is not None and "time" in arr.dims:
        arr = arr.isel(time=time_index)

    values = np.asarray(arr.values)
    values = np.squeeze(values)
    if values.ndim != 1:
        raise ValueError(f"expected 1D array, got shape={values.shape} for {da.name}")

    return values.astype(float, copy=False)


def build_wave_tiles_snapshot(
    lon: np.ndarray,
    lat: np.ndarray,
    height: np.ndarray,
    deg: np.ndarray,
    ikle2: np.ndarray,
    source_file: str,
    output_root: Path,
    min_z: int,
    max_z: int,
    time_index: int,
    target_tiles_by_zoom: dict[int, set[tuple[int, int]]] | None,
) -> None:
    valid_mask = (
        np.isfinite(lon)
        & np.isfinite(lat)
        & np.isfinite(height)
        & np.isfinite(deg)
    )
    valid_indices = np.where(valid_mask)[0]

    for z in range(min_z, max_z + 1):
        target_tiles = None
        if target_tiles_by_zoom is not None:
            target_tiles = target_tiles_by_zoom.get(z)

        buckets: dict[tuple[int, int], list[dict]] = defaultdict(list)
        point_tile = np.empty((len(lon), 2), dtype=np.int64)
        tile_node_mask = np.zeros(len(lon), dtype=bool)

        for idx in valid_indices:
            tile_x, tile_y = lonlat_to_xyz_tile(float(lon[idx]), float(lat[idx]), z)
            point_tile[idx, 0] = tile_x
            point_tile[idx, 1] = tile_y
            if target_tiles is not None and (tile_x, tile_y) not in target_tiles:
                continue

            tile_node_mask[idx] = True
            buckets[(tile_x, tile_y)].append(
                {
                    "idx": int(idx),
                    "lat": float(lat[idx]),
                    "lon": float(lon[idx]),
                    "deg": float(deg[idx]),
                    "height": float(height[idx]),
                }
            )

        triangles = subset_connectivity(ikle2, tile_node_mask)
        tri_buckets: dict[tuple[int, int], list[list[int]]] = defaultdict(list)
        for tri in triangles:
            tri_list = [int(v) for v in tri]
            tiles = {(int(point_tile[v, 0]), int(point_tile[v, 1])) for v in tri}
            for tile in tiles:
                if target_tiles is None or tile in target_tiles:
                    tri_buckets[tile].append(tri_list)

        z_dir = output_root / str(z)
        z_dir.mkdir(parents=True, exist_ok=True)

        with open(z_dir / "connectivity.json", "w", encoding="utf-8") as f:
            json.dump({"connectivity": triangles.tolist()}, f, ensure_ascii=False)

        for (tile_x, tile_y), points in buckets.items():
            x_dir = z_dir / str(tile_x)
            x_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "z": z,
                "x": tile_x,
                "y": tile_y,
                "time_index": time_index,
                "points": points,
                "connectivity": tri_buckets.get((tile_x, tile_y), []),
            }
            with open(x_dir / f"{tile_y}.json", "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)

        meta = {
            "source_file": source_file,
            "zoom": z,
            "time_index": time_index,
            "point_count": int(tile_node_mask.sum()),
            "triangle_count": int(len(triangles)),
            "tile_count": len(buckets),
            "fields": [
                "idx",
                "lat",
                "lon",
                "deg",
                "height",
            ],
        }
        with open(z_dir / "meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        print(
            f"[z{z}] "
            f"points={meta['point_count']} triangles={meta['triangle_count']} "
            f"tiles={meta['tile_count']}"
        )


def build_wave_tiles(
    slf_path: Path,
    output_root: Path,
    min_z: int,
    max_z: int,
    time_index: int,
    use_default_subset: bool,
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] read: {slf_path}")
    ds = xr.open_dataset(slf_path, engine="selafin")
    ds_time_values = ds.coords["time"].values
    max_time_index = len(ds_time_values) - 1
    if time_index < 0 or time_index > max_time_index:
        raise ValueError(
            f"time index out of range: {time_index}. valid range=0-{max_time_index}"
        )

    lon = to_numpy_1d(ds.coords["x"])
    lat = to_numpy_1d(ds.coords["y"])
    height_name = find_data_var(ds, ["WH"])
    deg_name = find_data_var(ds, ["THETAW"])

    ikle2 = np.asarray(ds.attrs["ikle2"])
    if ikle2.min() >= 1:
        ikle2 = ikle2 - 1

    target_tiles_by_zoom = None
    if use_default_subset:
        target_tiles_by_zoom = {}
        if min_z <= 11 <= max_z:
            target_tiles_by_zoom[11] = collect_target_tiles(Z11_SUBSET_TILES)

    print(
        "[2/3] variables: "
        f"height={height_name}, deg={deg_name}"
    )
    height = to_numpy_1d(ds[height_name], time_index=time_index)
    deg = to_numpy_1d(ds[deg_name], time_index=time_index)

    build_wave_tiles_snapshot(
        lon=lon,
        lat=lat,
        height=height,
        deg=deg,
        ikle2=ikle2,
        source_file=str(slf_path),
        output_root=output_root,
        min_z=min_z,
        max_z=max_z,
        time_index=time_index,
        target_tiles_by_zoom=target_tiles_by_zoom,
    )

    ds.close()
    print("[3/3] done")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slf", default=str(SLF_PATH), help="Input wave KOREA SLF path")
    parser.add_argument(
        "--output",
        default=str(OUTPUT_ROOT),
        help="Output root for wave tile subset",
    )
    parser.add_argument("--min-z", type=int, default=11)
    parser.add_argument("--max-z", type=int, default=11)
    parser.add_argument("--time-index", type=int, default=0)
    parser.add_argument(
        "--all-tiles",
        action="store_true",
        help="Build every tile instead of the default z11 port subset.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_wave_tiles(
        slf_path=Path(args.slf).expanduser().resolve(),
        output_root=Path(args.output).expanduser().resolve(),
        min_z=args.min_z,
        max_z=args.max_z,
        time_index=args.time_index,
        use_default_subset=not args.all_tiles,
    )


if __name__ == "__main__":
    main()
