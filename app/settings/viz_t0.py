"""t=0에서 부산 해역의 H(수심)를 해안선과 함께 시각화한다."""
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from shapely.geometry import box

from app.settings.data_processing import DATA_FILE

# 부산 해역 bbox (대략 가덕도 ~ 기장, 남쪽 먼바다 포함)
BUSAN_LON_MIN, BUSAN_LON_MAX = 128.7, 129.4
BUSAN_LAT_MIN, BUSAN_LAT_MAX = 34.7, 35.4

COASTLINE_PATH = Path(__file__).resolve().parents[2] / "data" / "coastline_clean.geojson"


def main() -> None:
    ds = xr.open_dataset(DATA_FILE, engine="selafin")
    ds0 = ds.isel(time=0)

    lon = ds0.coords["x"].values
    lat = ds0.coords["y"].values
    H = ds0["H"].values

    print(f"nodes : {len(lon)}")
    print(f"H@t0 range: {H.min():.2f} ~ {H.max():.2f} m")

    in_view = (
        (lon >= BUSAN_LON_MIN) & (lon <= BUSAN_LON_MAX)
        & (lat >= BUSAN_LAT_MIN) & (lat <= BUSAN_LAT_MAX)
    )
    print(f"busan bbox: lon[{BUSAN_LON_MIN},{BUSAN_LON_MAX}] "
          f"lat[{BUSAN_LAT_MIN},{BUSAN_LAT_MAX}]  nodes={in_view.sum()}")

    lon_v, lat_v, H_v = lon[in_view], lat[in_view], H[in_view]

    bbox = box(BUSAN_LON_MIN, BUSAN_LAT_MIN, BUSAN_LON_MAX, BUSAN_LAT_MAX)
    coast = gpd.read_file(COASTLINE_PATH, bbox=bbox)
    print(f"coastline features in view: {len(coast)}")

    fig, ax = plt.subplots(figsize=(9, 9), constrained_layout=True)
    sc = ax.scatter(lon_v, lat_v, s=2.5, c=H_v, cmap="viridis",
                    vmin=0, vmax=np.percentile(H_v, 99), zorder=1)
    coast.plot(ax=ax, color="black", linewidth=0.6, zorder=2)

    ax.set_title(f"H (water depth)  t=0  — Busan\n"
                 f"range {H_v.min():.2f} ~ {H_v.max():.2f} m  (n={in_view.sum()})")
    plt.colorbar(sc, ax=ax, shrink=0.8, label="H [m]")

    ax.set_xlim(BUSAN_LON_MIN, BUSAN_LON_MAX)
    ax.set_ylim(BUSAN_LAT_MIN, BUSAN_LAT_MAX)
    ax.set_aspect("equal")
    ax.set_xlabel("lon")
    ax.set_ylabel("lat")

    out = Path(__file__).parent / "viz_t0.png"
    fig.savefig(out, dpi=150)
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()
