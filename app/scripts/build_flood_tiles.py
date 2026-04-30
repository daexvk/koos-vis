from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import xarray as xr

from app.settings.mesh_utils import subset_connectivity
from app.settings.tile_utils import lonlat_to_xyz_tile


SLF_PATH = Path.home() / "data" / "0314_surge_res_korea.slf"
OUTPUT_ROOT = Path.home() / "data" / "flood_tiles"


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


def find_data_var(ds: xr.Dataset, candidates: list[str]) -> str:
    lower_map = {name.lower(): name for name in ds.data_vars}
    for cand in candidates:
        key = cand.lower()
        if key in lower_map:
            return lower_map[key]

    for cand in candidates:
        key = cand.lower()
        for name in ds.data_vars:
            if key in name.lower():
                return name

    raise ValueError(
        f"variable not found. candidates={candidates}, available={list(ds.data_vars)}"
    )


def find_coord_var(ds: xr.Dataset, candidates: list[str]) -> str:
    lower_map = {name.lower(): name for name in ds.variables}
    for cand in candidates:
        key = cand.lower()
        if key in lower_map:
            return lower_map[key]

    for cand in candidates:
        key = cand.lower()
        for name in ds.variables:
            if key in name.lower():
                return name

    raise ValueError(
        f"coord variable not found. candidates={candidates}, available={list(ds.variables)}"
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


def get_slf_variable_names(ds: xr.Dataset) -> tuple[str, str, str, str]:
    lon_name = find_coord_var(ds, ["meshx", "lon", "longitude", "x"])
    lat_name = find_coord_var(ds, ["meshy", "lat", "latitude", "y"])
    s_name = find_data_var(ds, ["s", "free_surface", "water_surface", "ssh"])
    h_name = find_data_var(ds, ["h", "water_depth", "depth"])
    return lon_name, lat_name, s_name, h_name


def load_slf_snapshot(slf_path: Path, time_index: int = 0):
    ds = xr.open_dataset(slf_path, engine="selafin")
    lon_name, lat_name, s_name, h_name = get_slf_variable_names(ds)

    lon = to_numpy_1d(ds[lon_name])
    lat = to_numpy_1d(ds[lat_name])
    s = to_numpy_1d(ds[s_name], time_index=time_index)
    h = to_numpy_1d(ds[h_name], time_index=time_index)

    ikle2 = np.asarray(ds.attrs["ikle2"])
    if ikle2.min() >= 1:
        ikle2 = ikle2 - 1

    ds.close()
    return lon, lat, s, h, ikle2


def build_flood_tiles_for_time(
    lon: np.ndarray,
    lat: np.ndarray,
    s: np.ndarray,
    h: np.ndarray,
    ikle2: np.ndarray,
    source_file: str,
    output_root: Path,
    min_z: int,
    max_z: int,
    time_index: int = 0,
) -> None:
    raw_flood = s - h
    flood = np.where(np.isfinite(raw_flood), np.maximum(raw_flood, 0.0), np.nan)

    valid_mask = (
        np.isfinite(lon)
        & np.isfinite(lat)
        & np.isfinite(flood)
    )

    valid_indices = np.where(valid_mask)[0]
    positive_count = int((flood[valid_mask] > 0).sum())

    triangles = subset_connectivity(ikle2, valid_mask)
    triangles_list = triangles.tolist()

    print(
        f"[2/3] valid nodes: {len(valid_indices)}, "
        f"flooded nodes: {positive_count}, triangles: {len(triangles)}"
    )

    for z in range(min_z, max_z + 1):
        buckets: dict[tuple[int, int], list[dict]] = defaultdict(list)

        for idx in valid_indices:
            tx, ty = lonlat_to_xyz_tile(float(lon[idx]), float(lat[idx]), z)
            buckets[(tx, ty)].append(
                {
                    "idx": int(idx),
                    "lat": float(lat[idx]),
                    "lon": float(lon[idx]),
                    "flood": float(flood[idx]),
                }
            )

        z_dir = output_root / f"t{time_index}" / str(z)
        z_dir.mkdir(parents=True, exist_ok=True)

        with open(z_dir / "connectivity.json", "w", encoding="utf-8") as f:
            json.dump({"triangles": triangles_list}, f, ensure_ascii=False)

        for (tile_x, tile_y), points in buckets.items():
            x_dir = z_dir / str(tile_x)
            x_dir.mkdir(parents=True, exist_ok=True)

            payload = {
                "z": z,
                "x": tile_x,
                "y": tile_y,
                "time_index": time_index,
                "points": points,
            }

            with open(x_dir / f"{tile_y}.json", "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)

        meta = {
            "source_file": source_file,
            "zoom": z,
            "time_index": time_index,
            "point_count": len(valid_indices),
            "flooded_point_count": positive_count,
            "triangle_count": int(len(triangles)),
            "tile_count": len(buckets),
            "fields": ["idx", "lat", "lon", "flood"],
        }

        with open(z_dir / "meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        print(f"[zoom {z}] tiles={len(buckets)}")

    print("[3/3] done")


def build_flood_tiles(
    slf_path: Path,
    output_root: Path,
    min_z: int = 11,
    max_z: int = 13,
    time_indices: list[int] | None = None,
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    if time_indices is None:
        time_indices = [0]

    print(f"[1/3] read: {slf_path}")
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

    lon_name, lat_name, s_name, h_name = get_slf_variable_names(ds)
    lon = to_numpy_1d(ds[lon_name])
    lat = to_numpy_1d(ds[lat_name])
    ikle2 = np.asarray(ds.attrs["ikle2"])
    if ikle2.min() >= 1:
        ikle2 = ikle2 - 1

    write_times_meta(output_root, ds_time_values, str(slf_path), time_indices)

    for time_index in time_indices:
        print(f"[time {time_index}] build flood tiles")
        s = to_numpy_1d(ds[s_name], time_index=time_index)
        h = to_numpy_1d(ds[h_name], time_index=time_index)
        build_flood_tiles_for_time(
            lon=lon,
            lat=lat,
            s=s,
            h=h,
            ikle2=ikle2,
            source_file=str(slf_path),
            output_root=output_root,
            min_z=min_z,
            max_z=max_z,
            time_index=time_index,
        )

    ds.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slf", default=str(SLF_PATH), help="Input SLF path")
    parser.add_argument(
        "--output",
        default=str(OUTPUT_ROOT),
        help="Output root for flood tiles",
    )
    parser.add_argument("--min-z", type=int, default=11)
    parser.add_argument("--max-z", type=int, default=13)
    parser.add_argument("--time-index", type=int, default=0)
    parser.add_argument(
        "--time-indices",
        default=None,
        help="Comma-separated time indices or inclusive ranges, e.g. 0,1,2 or 0-24",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_flood_tiles(
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
