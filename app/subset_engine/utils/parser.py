import struct
from pathlib import Path
from typing import BinaryIO, TypedDict

import numpy as np

from app.subset_engine.schemas import TimestepData
from app.subset_engine.utils.info import load_alias_map, read_record

_ALIAS_MAP = load_alias_map()


class SlfHeader(TypedDict):
    title: str
    format: str
    variables: list[tuple[str, str]]
    iparam: tuple[int, ...]
    date_start: tuple[int, int, int, int, int, int] | None
    nelem: int
    npoin: int
    ndp: int
    ikle: np.ndarray
    ipobo: np.ndarray
    x: np.ndarray
    y: np.ndarray
    float_dtype: str
    float_size: int
    body_offset: int


def read_header(f: BinaryIO) -> SlfHeader:
    rec1 = read_record(f)
    title = rec1[:72].decode("ascii", errors="replace").strip()
    fmt = rec1[72:80].decode("ascii", errors="replace").strip()

    nbv1, _nbv2 = struct.unpack(">ii", read_record(f))
    variables: list[tuple[str, str]] = []
    for _ in range(nbv1):
        rec = read_record(f)
        name = rec[:16].decode("ascii", errors="replace").strip()
        unit = rec[16:32].decode("ascii", errors="replace").strip()
        variables.append((name, unit))

    iparam = struct.unpack(">10i", read_record(f))
    date_start = struct.unpack(">6i", read_record(f)) if iparam[9] == 1 else None

    nelem, npoin, ndp, _ = struct.unpack(">4i", read_record(f))
    ikle = np.frombuffer(read_record(f), dtype=">i4").reshape(nelem, ndp)
    ipobo = np.frombuffer(read_record(f), dtype=">i4")

    x_raw = read_record(f)
    float_size = len(x_raw) // npoin
    float_dtype = ">f8" if float_size == 8 else ">f4"
    x = np.frombuffer(x_raw, dtype=float_dtype)
    y = np.frombuffer(read_record(f), dtype=float_dtype)

    return {
        "title": title,
        "format": fmt,
        "variables": variables,
        "iparam": iparam,
        "date_start": date_start,
        "nelem": nelem,
        "npoin": npoin,
        "ndp": ndp,
        "ikle": ikle,
        "ipobo": ipobo,
        "x": x,
        "y": y,
        "float_dtype": float_dtype,
        "float_size": float_size,
        "body_offset": f.tell(),
    }


def read_start_time(path: str | Path) -> tuple[int, int, int, int, int, int] | None:
    """Return the (year, month, day, hour, minute, second) start time from the SLF header,
    or None if the file has no date_start record (iparam[9] != 1)."""
    with open(path, "rb") as f:
        return read_header(f)["date_start"]


def step_bytes(header: SlfHeader) -> int:
    nbv1 = len(header["variables"])
    npoin = header["npoin"]
    fs = header["float_size"]
    # Each Fortran-style record = 4-byte size prefix + payload + 4-byte size suffix.
    return (4 + fs + 4) + nbv1 * (4 + npoin * fs + 4)


def num_timesteps(path: str | Path) -> int:
    path = Path(path)
    with open(path, "rb") as f:
        header = read_header(f)
    body_size = path.stat().st_size - header["body_offset"]
    sb = step_bytes(header)
    if body_size % sb != 0:
        raise ValueError(f"body size {body_size} not divisible by step size {sb}")
    return body_size // sb


def read_timestep_at(
    f: BinaryIO,
    header: SlfHeader,
    sb: int,
    total: int,
    time_index: int,
) -> TimestepData:
    """같은 파일에서 여러 timestep을 읽을 때 헤더/오픈을 재사용하는 코어 루틴.

    호출자가 파일을 한 번만 열고 read_header/step_bytes/total을 미리 구해서 넘겨주면,
    이 함수는 timestep당 seek + 필요한 record만 읽는다.
    """
    idx = time_index + total if time_index < 0 else time_index
    if not 0 <= idx < total:
        raise IndexError(f"time_index {time_index} out of range (total={total})")

    f.seek(header["body_offset"] + idx * sb)

    time_fmt = ">d" if header["float_size"] == 8 else ">f"
    time_val = float(struct.unpack(time_fmt, read_record(f))[0])

    ds: dict[str, np.ndarray] = {"x": header["x"], "y": header["y"]}
    for name, _unit in header["variables"]:
        key = _ALIAS_MAP.get(name.upper(), name)
        ds[key] = np.frombuffer(read_record(f), dtype=header["float_dtype"])

    # SLF IKLE is 1-based (Fortran); bucket_by_tile indexes ds[...] with these ids.
    triangles = header["ikle"].astype(np.int64) - 1

    return {
        "time": time_val,
        "ds": ds,
        "triangles": triangles,
    }


def read_timestep(
    path: str | Path,
    time_index: int,
) -> TimestepData:
    """Extract a single time step in a shape ready for bucket_by_tile.

    Args:
        path: path to the .slf file
        time_index: 0-based time-step index (negative indices count from the end)

    Returns:
        TimestepData — passable directly to bucket_by_tile; 'time' is seconds since
        header['date_start'].
    """
    path = Path(path)
    with open(path, "rb") as f:
        header = read_header(f)
        sb = step_bytes(header)
        total = (path.stat().st_size - header["body_offset"]) // sb
        return read_timestep_at(f, header, sb, total, time_index)
