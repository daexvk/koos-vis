import struct
from datetime import datetime, timedelta
from pathlib import Path

from app.subset_engine.utils.info import read_record
from app.subset_engine.utils.parser import read_header, step_bytes


def get_hourly_indicies(path: str | Path, tol: float = 1e-3) -> list[tuple[int, str]]:
    """(index, formatted-timestamp) for timesteps that land exactly on the hour.

    Timesteps are uniformly spaced; dt는 t[0]·t[1]만 읽어 산술로 결정한다.

    TODO: 현재는 date_start가 정각(min=0, sec=0)이라 가정. date_start의 sub-hour
    offset(=min*60+sec)을 고려해, 절대 시각이 정각인 step만 emit하도록 확장 필요.
    구체적으로 offset_to_hour 계산을 (-t0 - sub_hour_offset) % 3600.0로 바꾸고,
    date_start=None인 경우 현재 동작 유지.
    """
    path = Path(path)
    with open(path, "rb") as f:
        header = read_header(f)
        sb = step_bytes(header)
        total = (path.stat().st_size - header["body_offset"]) // sb
        time_fmt = ">d" if header["float_size"] == 8 else ">f"

        def time_at(i: int) -> float:
            f.seek(header["body_offset"] + i * sb)
            return float(struct.unpack(time_fmt, read_record(f))[0])

        t0 = time_at(0)
        dt = time_at(1) - t0 if total > 1 else 3600.0
        date_start = header["date_start"]

    if dt <= 0:
        raise ValueError(f"non-positive timestep dt={dt}")

    steps_per_hour = 3600.0 / dt
    if abs(steps_per_hour - round(steps_per_hour)) > tol:
        raise ValueError(f"dt={dt}s does not divide 3600s evenly")
    step = int(round(steps_per_hour))

    offset_to_hour = (-t0) % 3600.0
    start_steps = offset_to_hour / dt
    if abs(start_steps - round(start_steps)) > tol:
        raise ValueError(f"t0={t0} not aligned to {dt}s grid hour boundary")
    start = int(round(start_steps))

    return [(i, format_timestamp(date_start, t0 + i * dt)) for i in range(start, total, step)]


def format_timestamp(date_start: tuple | None, secs: float) -> str:
    """Format seconds-from-start as ISO 8601, or '<secs>s' if date_start is None."""
    s = int(round(secs))
    if date_start is None:
        return f"{s}s"
    return (datetime(*date_start) + timedelta(seconds=s)).isoformat()
