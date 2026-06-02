from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from app.settings.tile_utils import (
    bucket_nodes, collect_target_tiles, save_meta, save_tiles,
)
from app.settings.mesh_utils import stride_coarsen_mesh, subset_connectivity


DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "0314_surge_res_korea.slf"
CACHE_ROOT = DATA_FILE.parent / "tiles"

def process_zoom_level(
    ds: xr.Dataset,
    zoom: int,
    cache_root: Path,
    *,
    stride: int | None = None,
    target_tiles: set[tuple[int, int, int]] | None = None,
) -> tuple[int, int, int]:
    """특정 줌 레벨에 대해 coarsen(optional) + 서브셋 + 타일 저장을 수행한다."""
    ds0 = ds.isel(time=0)
    lon, lat = ds0.coords["x"].values, ds0.coords["y"].values
    h = ds0["H"].values

    ikle2 = np.array(ds.attrs["ikle2"])
    if ikle2.min() >= 1:
        ikle2 -= 1

    if stride is not None:
        ipobo = np.array(ds.attrs["ipobo"])
        keep_mask, simplices = stride_coarsen_mesh(ikle2, lon, lat, ipobo, stride)
        keep_idx = np.where(keep_mask)[0]
        lon_k, lat_k, h_k = lon[keep_idx], lat[keep_idx], h[keep_idx]
        print(f"z{zoom} stride coarsen: {len(keep_idx)} nodes, {len(simplices)} triangles")
        buckets = bucket_nodes(lon_k, lat_k, h_k, zoom, target_tiles, indices=keep_idx)
    else:
        simplices = ikle2
        buckets = bucket_nodes(lon, lat, h, zoom, target_tiles)

    if target_tiles is not None and stride is None:
        node_mask = np.zeros(len(lon), dtype=bool)
        for pts in buckets.values():
            for pt in pts:
                node_mask[pt["idx"]] = True
        simplices = subset_connectivity(ikle2, node_mask)

    n_nodes = len(keep_idx) if stride is not None else len(lon)
    save_tiles(cache_root / str(zoom), zoom, buckets, simplices)
    print(f"z{zoom}: {len(simplices)} tri, {n_nodes} nodes, {len(buckets)} tiles")

    return n_nodes, len(simplices), len(buckets)


def main() -> None:
    STRIDE = 10
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)

    ds = xr.open_dataset(DATA_FILE, engine="selafin")

    # --- zoom 6 (coarsened). 전국 데이터 타일링 ---
    n_pts, n_tri, n_tiles = process_zoom_level(
        ds, 6, CACHE_ROOT, stride=STRIDE,
    )
    save_meta(CACHE_ROOT, ds.coords["time"].values, str(DATA_FILE),
              6, STRIDE, n_pts, n_tri, n_tiles)

    # --- zoom 11 (original). 항구별 데이터 타일링 ---
    Z11_SUBSET_TILES = {
        "jinhae":   (11, 1756, 810),
        "busan":    (11, 1758, 810),
        "donghae":  (11, 1758, 793),
        "gangjeong": (11, 1743, 823),
        "mokpo":    (11, 1743, 812),
    }
    target_tiles = collect_target_tiles(Z11_SUBSET_TILES)
    process_zoom_level(ds, 11, CACHE_ROOT, target_tiles=target_tiles)

    print("preprocess complete")


if __name__ == "__main__":
    main()
