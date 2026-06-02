import csv
import struct
import sys
from pathlib import Path

import numpy as np
import xarray_selafin

DOUT_ROOT = Path("/Volumes/T7/sample/NSTORM/DOUT")

IPARAM_LABELS = [
    "[0] x-origin shift",
    "[1] y-origin shift",
    "[2] reserved",
    "[3] num planes (3D, =0 for 2D)",
    "[4] reserved",
    "[5] reserved",
    "[6] mesh-numbering offset (NPTFR)",
    "[7] reserved",
    "[8] reserved",
    "[9] date_start present (0/1)",
]


def load_alias_map() -> dict[str, str]:
    pkg_dir = Path(xarray_selafin.__file__).parent
    csv_path = pkg_dir / "data" / "Serafin_var2D.csv"
    mapping: dict[str, str] = {}
    with open(csv_path) as f:
        for alias, _french, english, _unit in csv.reader(f, delimiter=";"):
            mapping[english.strip().upper()] = alias.strip()
    return mapping


def read_record(f) -> bytes:
    size = struct.unpack(">i", f.read(4))[0]
    data = f.read(size)
    f.read(4)
    return data


def dump_slf(path: Path, alias_map: dict) -> None:
    print("=" * 100)
    print(f"file: {path}")
    print(f"size: {path.stat().st_size:,} bytes")

    with open(path, "rb") as f:
        rec1 = read_record(f)
        title = rec1[:72].decode("ascii", errors="replace").strip()
        fmt = rec1[72:80].decode("ascii", errors="replace").strip()
        print(f"  title : {title!r}")
        print(f"  format: {fmt!r}")

        nbv1, nbv2 = struct.unpack(">ii", read_record(f))
        print(f"  nbv1 (linear): {nbv1}   nbv2 (quad): {nbv2}")

        variables = []
        print(f"\n  variables ({nbv1}):  idx  xarray_key  header_name              unit")
        for k in range(nbv1):
            rec = read_record(f)
            name = rec[:16].decode("ascii", errors="replace").strip()
            unit = rec[16:32].decode("ascii", errors="replace").strip()
            variables.append((name, unit))
            key = alias_map.get(name.upper(), name)
            print(f"    {k:3d}  {key:<10s}  {name:<24s}  [{unit}]")

        iparam = struct.unpack(">10i", read_record(f))
        print(f"\n  iparam:")
        for v, lbl in zip(iparam, IPARAM_LABELS):
            print(f"    {lbl:<35s} = {v}")

        if iparam[9] == 1:
            date_start = struct.unpack(">6i", read_record(f))
            print(f"  date_start (Y,M,D,h,m,s) = {date_start}")
        else:
            print(f"  date_start: (none)")

        nelem, npoin, ndp, _ = struct.unpack(">4i", read_record(f))
        print(f"\n  mesh:")
        print(f"    nelem (#triangles): {nelem:,}")
        print(f"    npoin (#nodes)    : {npoin:,}")
        print(f"    ndp  (#nodes/elem): {ndp}")

        ikle = np.frombuffer(read_record(f), dtype=">i4").reshape(nelem, ndp)
        print(f"    IKLE  shape={ikle.shape}  min/max node id: {ikle.min()} / {ikle.max()}")

        ipobo = np.frombuffer(read_record(f), dtype=">i4")
        print(f"    IPOBO shape={ipobo.shape}  boundary nodes: {int(np.count_nonzero(ipobo)):,}")

        x_raw = read_record(f)
        float_size = len(x_raw) // npoin
        dtype = ">f8" if float_size == 8 else ">f4"
        x = np.frombuffer(x_raw, dtype=dtype)
        y = np.frombuffer(read_record(f), dtype=dtype)
        print(f"    X range: {x.min():.6f} ~ {x.max():.6f}   (float{float_size*8})")
        print(f"    Y range: {y.min():.6f} ~ {y.max():.6f}   (float{float_size*8})")


def main() -> None:
    args = sys.argv[1:]
    alias_map = load_alias_map()
    targets = [Path(a) for a in args] if args else sorted(DOUT_ROOT.rglob("*.slf"))
    for p in targets:
        try:
            dump_slf(p, alias_map)
        except Exception as e:
            print(f"[failed] {p}: {e}")


if __name__ == "__main__":
    main()
