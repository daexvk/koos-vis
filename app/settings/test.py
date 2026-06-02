import xarray as xr
from pathlib import Path

fp = Path(__file__).resolve().parents[2] / "data" / "0314_surge_res_korea.slf"
ds = xr.open_dataset(fp, engine="selafin")

print("=== DATASET ===")
print(ds)

print("\n=== COORDS HEAD ===")
for name in ds.coords:
    arr = ds.coords[name]
    print(name, arr.shape, arr.values[:5])

print("\n=== VARS ===")
for name in ds.data_vars:
    da = ds[name]
    print(name, da.dims, da.shape, da.dtype)

print("\n=== SAMPLE VALUES ===")
for name in ds.data_vars:
    da = ds[name].isel(time=0)
    print(name, da.values[:10])

print("\n=== MESH ===")
print("ikle2:", ds.attrs["ikle2"][:5])
print("ipobo:", ds.attrs["ipobo"][:10])

print(ds.attrs["variables"])
