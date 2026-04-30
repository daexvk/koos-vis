from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import xarray as xr

from app.settings.mesh_utils import subset_connectivity


SLF_PATH = Path.home() / "data" / "0314_surge_res_korea.slf"
OUTPUT_ROOT = Path.home() / "data" / "flood_tiles"


def lonlat_to_xyz_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    lat = max(min(lat, 85.05112878), -85.05112878)

    n = 2**z
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


def load_slf_snapshot(slf_path: Path, time_index: int = 0):
    ds = xr.open_dataset(slf_path, engine="selafin")

    lon_name = find_coord_var(ds, ["meshx", "lon", "longitude", "x"])
    lat_name = find_coord_var(ds, ["meshy", "lat", "latitude", "y"])

    s_name = find_data_var(ds, ["s", "free_surface", "water_surface", "ssh"])
    h_name = find_data_var(ds, ["h", "water_depth", "depth"])

    lon = to_numpy_1d(ds[lon_name])
    lat = to_numpy_1d(ds[lat_name])
    s = to_numpy_1d(ds[s_name], time_index=time_index)
    h = to_numpy_1d(ds[h_name], time_index=time_index)

    ikle2 = np.asarray(ds.attrs["ikle2"])
    if ikle2.min() >= 1:
        ikle2 = ikle2 - 1

    ds.close()
    return lon, lat, s, h, ikle2


def build_flood_tiles(
    slf_path: Path,
    output_root: Path,
    min_z: int = 11,
    max_z: int = 13,
    time_index: int = 0,
) -> None:
    print(f"[1/3] read: {slf_path}")
    lon, lat, s, h, ikle2 = load_slf_snapshot(slf_path, time_index=time_index)

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

    output_root.mkdir(parents=True, exist_ok=True)

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

        z_dir = output_root / str(z)
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
            "source_file": str(slf_path),
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


if __name__ == "__main__":
    build_flood_tiles(
        slf_path=SLF_PATH,
        output_root=OUTPUT_ROOT,
        min_z=11,
        max_z=13,
        time_index=0,
    )