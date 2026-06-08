import os
import json
from itertools import chain
from multiprocessing import Pool
from pathlib import Path
from typing import Callable, NamedTuple

import numpy as np

from app.subset_engine.logger import (
    advance_file_progress,
    end_file_progress,
    init_worker,
    start_file_progress,
)
from app.subset_engine.utils.tile import bucket_mesh_by_tile, bucket_values_by_tile
from app.subset_engine.utils.parser import (
    read_header,
    read_timestep,
    read_timestep_at,
    step_bytes,
)
from app.subset_engine.utils.time import get_hourly_indicies
from app.subset_engine.utils.file import (
    ensure_dir,
    make_file_readable,
    read_mesh_index_npz,
    write_mesh_index_npz,
    write_mesh_tile_bin,
    write_values_tile_bin,
)
from app.subset_engine.schemas import TimestepData


DEFAULT_LAYERS: dict[str, dict[str, list[str]]] = {
    "surge": {
        "height": ["H"],
        "tidal_height": ["S"],
        "current": ["U", "V"],
    },
    "wave": {
        "wave": ["WH", "THETAW"],
    },
}

WORKERS = 8
_MESH_INDEX_CACHE: dict[tuple[str, int], dict[tuple[int, int], dict]] = {}
VALUE_COMPLETE_MARKER = ".complete.json"
MESH_FORMAT_VERSION = 3


class FilenameParts(NamedTuple):
    typhoon_id: str
    scenario_id: str
    model_type: str
    location: str


class TimeIndexRange(NamedTuple):
    start: int
    stop: int
    items: list[tuple[int, str]]


def parse_filename(filepath: Path | str) -> FilenameParts:
    parts = Path(filepath).stem.split("_")
    return FilenameParts(
        typhoon_id=parts[0],
        scenario_id=parts[1],
        model_type=parts[2],
        location=parts[-1],
    )


def resolve_zooms(target_zooms: dict[str, list[int]], location: str) -> list[int]:
    """location별 zoom 목록을 분기. 등록되지 않은 location은 'default' 항목을 사용."""
    return target_zooms.get(location, target_zooms["default"])


def _compute_land_mask(surge_path: Path | str | None, npoin: int) -> np.ndarray | None:
    """SURGE 파일 timestep0에서 육지 마스크(bottom = S - H > 0)를 계산.

    bottom = FREE SURFACE - WATER DEPTH 는 시간 불변인 해저고도이므로 timestep0만 읽으면 충분.
    파일이 없거나 S/H가 없거나 노드 수가 안 맞으면 None.
    """
    if surge_path is None:
        return None
    try:
        ds = read_timestep(surge_path, 0)["ds"]
        s = np.asarray(ds["S"])
        h = np.asarray(ds["H"])
    except (KeyError, OSError, ValueError, IndexError):
        return None
    if s.shape != h.shape or s.shape[0] != npoin:
        return None
    return (s - h) > 0


def _compute_mesh_tiles(
    filepath: Path | str, zooms: list[int], surge_file: Path | str | None
) -> dict[int, dict[tuple[int, int], dict]]:
    with open(filepath, "rb") as f:
        header = read_header(f)
    x = np.asarray(header["x"])
    y = np.asarray(header["y"])
    triangles = header["ikle"].astype(np.int64) - 1
    land_mask = _compute_land_mask(surge_file, header["npoin"])
    return {z: bucket_mesh_by_tile(x, y, triangles, z, land_mask) for z in zooms}


def _mesh_index_path(
    sample_out: str | Path,
    location: str,
    zoom: int,
) -> Path:
    return Path(sample_out) / "mesh_index" / location / f"{zoom}.npz"


def _write_mesh_outputs(
    mesh_root: Path,
    index_root: str | Path,
    location: str,
    z: int,
    tiles: dict[tuple[int, int], dict],
) -> None:
    zx_dirs: dict[int, str] = {}
    for (tx, ty), tile in tiles.items():
        tile_dir = zx_dirs.get(tx)
        if tile_dir is None:
            tile_dir = ensure_dir(mesh_root, z, tx)
            zx_dirs[tx] = tile_dir
        write_mesh_tile_bin(os.path.join(tile_dir, f"{ty}.bin"), tile)

    write_mesh_index_npz(
        _mesh_index_path(index_root, location, z),
        tiles,
    )


def _load_mesh_index(
    sample_out: str | Path,
    location: str,
    zoom: int,
) -> dict[tuple[int, int], dict]:
    key = (location, zoom)
    cached = _MESH_INDEX_CACHE.get(key)
    if cached is not None:
        return cached

    path = _mesh_index_path(sample_out, location, zoom)
    if not path.exists():
        raise FileNotFoundError(f"mesh index not found: {path}")

    tiles = read_mesh_index_npz(path)
    _MESH_INDEX_CACHE[key] = tiles
    return tiles


def _load_mesh_indices(
    sample_out: str | Path,
    location: str,
    zooms: list[int],
) -> dict[int, dict[tuple[int, int], dict]]:
    return {
        z: _load_mesh_index(sample_out, location, z)
        for z in zooms
    }


def _mesh_complete_path(mesh_root: Path, z: int) -> Path:
    return mesh_root / str(z) / ".complete"


def _mesh_outputs_current(mesh_root: Path, z: int, index_path: Path) -> bool:
    complete_path = _mesh_complete_path(mesh_root, z)
    if not complete_path.exists() or not index_path.exists():
        return False

    try:
        with open(complete_path, "r", encoding="utf-8") as f:
            marker = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False

    return marker.get("mesh_format_version") == MESH_FORMAT_VERSION


def _write_mesh_complete_marker(mesh_root: Path, z: int) -> None:
    complete_path = _mesh_complete_path(mesh_root, z)
    with open(complete_path, "w", encoding="utf-8") as f:
        json.dump({"mesh_format_version": MESH_FORMAT_VERSION}, f)
    make_file_readable(complete_path)


def tile_mesh_for_group(
    rep_file: Path | str,
    surge_file: Path | str | None,
    zooms: list[int],
    sample_out: str | Path,
    location: str,
) -> None:
    """대표 .slf 한 파일에서 메쉬를 zoom별로 타일링해 sample_out/mesh/{location}/에 저장.

    SURGE/WAVE 메쉬가 동일하므로 location당 1벌만 저장한다. 육지 마스크(land_nodes)는
    surge_file(같은 location의 SURGE)에서 계산해 함께 담는다.

    각 zoom 디렉토리에 .complete 마커 파일이 있는 경우 그 zoom은 건너뜀.
    마커는 모든 타일을 다 쓴 뒤 마지막에 생성해 부분 실패 시 재실행으로 복구 가능.
    같은 계산 결과에서 값 서브세팅용 mesh_index/{location}/{zoom}.npz도 함께 저장한다.
    """
    mesh_root = Path(sample_out) / "mesh" / location
    pending = [
        z
        for z in zooms
        if not _mesh_outputs_current(
            mesh_root,
            z,
            _mesh_index_path(sample_out, location, z),
        )
    ]
    if not pending:
        return
    ensure_dir(mesh_root)
    mesh_tiles_per_zoom = _compute_mesh_tiles(rep_file, pending, surge_file)
    for z, tiles in mesh_tiles_per_zoom.items():
        _write_mesh_outputs(mesh_root, sample_out, location, z, tiles)
        _write_mesh_complete_marker(mesh_root, z)


def subset_layer(
    timestep_data: TimestepData,
    time: str,
    target_dir: str | Path,
    zooms: list[int],
    layer_name: str,
    value_keys: list[str],
    mesh_tiles_per_zoom: dict[int, dict[tuple[int, int], dict]],
):
    layer_dir = ensure_dir(target_dir, layer_name)
    time_dir = ensure_dir(layer_dir, time)
    ds = timestep_data["ds"]
    for z in zooms:
        value_tiles = bucket_values_by_tile(ds, mesh_tiles_per_zoom[z], value_keys)
        zx_dirs: dict[int, str] = {}
        for (x, y), tile in value_tiles.items():
            tile_dir = zx_dirs.get(x)
            if tile_dir is None:
                tile_dir = ensure_dir(time_dir, z, x)
                zx_dirs[x] = tile_dir
            write_values_tile_bin(os.path.join(tile_dir, f"{y}.bin"), tile, value_keys)


def _target_dir_for_file(
    filepath: Path | str,
    sample_out: str | Path,
) -> Path:
    parts = parse_filename(filepath)
    return (
        Path(sample_out)
        / parts.typhoon_id
        / parts.location
        / parts.model_type
        / parts.scenario_id
    )


def _value_complete_marker_path(target_dir: str | Path) -> Path:
    return Path(target_dir) / VALUE_COMPLETE_MARKER


def _source_signature(filepath: Path | str) -> dict:
    path = Path(filepath)
    stat = path.stat()
    return {
        "source": str(path),
        "source_size": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
    }


def _value_outputs_marked_complete(filepath: Path | str, target_dir: str | Path) -> bool:
    marker_path = _value_complete_marker_path(target_dir)
    if not marker_path.exists():
        return False

    try:
        with open(marker_path, "r", encoding="utf-8") as f:
            marker = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False

    signature = _source_signature(filepath)
    return (
        marker.get("source_size") == signature["source_size"]
        and marker.get("source_mtime_ns") == signature["source_mtime_ns"]
    )


def _write_value_complete_marker(
    filepath: Path | str,
    target_dir: str | Path,
    target_layers: dict[str, list[str]],
) -> None:
    marker_path = _value_complete_marker_path(target_dir)
    payload = {
        **_source_signature(filepath),
        "layers": sorted(target_layers),
    }
    with open(marker_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    make_file_readable(marker_path)


def _time_outputs_complete(
    target_dir: str | Path,
    target_layers: dict[str, list[str]],
    time: str,
    zooms: list[int],
    mesh_tiles_per_zoom: dict[int, dict[tuple[int, int], dict]],
) -> bool:
    base = Path(target_dir)
    for layer_name in target_layers:
        for z in zooms:
            for x, y in mesh_tiles_per_zoom[z]:
                path = base / layer_name / time / str(z) / str(x) / f"{y}.bin"
                if not path.exists():
                    return False
    return True


def _filter_pending_indices(
    hourly: list[tuple[int, str]],
    target_dir: str | Path,
    target_layers: dict[str, list[str]],
    zooms: list[int],
    mesh_tiles_per_zoom: dict[int, dict[tuple[int, int], dict]],
) -> list[tuple[int, str]]:
    return [
        (idx, time)
        for idx, time in hourly
        if not _time_outputs_complete(
            target_dir,
            target_layers,
            time,
            zooms,
            mesh_tiles_per_zoom,
        )
    ]


def _prepare_file(
    filepath: Path,
    target_zooms: dict[str, list[int]],
    sample_out: str | Path,
    layers: dict[str, dict[str, list[str]]],
):
    """파일 메타데이터 준비 + mesh 1회 타일링. 메인 프로세스에서 호출됨.

    filepath 예시: /some/path/0314_01_surge_res_busan.slf
    target_zooms 예시: {"korea": [6,7,8,9], "default": [10,11,12]}
    """
    parts = parse_filename(filepath)
    target_dir = ensure_dir(
        sample_out, parts.typhoon_id, parts.location, parts.model_type, parts.scenario_id
    )
    target_layers = layers[parts.model_type]
    zooms = resolve_zooms(target_zooms, parts.location)
    mesh_tiles_per_zoom = _load_mesh_indices(
        sample_out,
        parts.location,
        zooms,
    )
    hourly = get_hourly_indicies(filepath)
    return target_dir, target_layers, zooms, mesh_tiles_per_zoom, hourly


def _split_time_index_ranges(
    indices: list[tuple[int, str]], workers: int
) -> list[TimeIndexRange]:
    """hourly time index 목록을 최대 workers개 range로 거의 균등 분할."""
    if not indices:
        return []
    workers = min(workers, len(indices))
    k, r = divmod(len(indices), workers)
    out: list[TimeIndexRange] = []
    start = 0
    for i in range(workers):
        size = k + (1 if i < r else 0)
        stop = start + size
        out.append(TimeIndexRange(start=start, stop=stop, items=indices[start:stop]))
        start = stop
    return out


def _process_time_index_range(args) -> None:
    (
        filepath,
        time_index_range,
        target_dir,
        target_layers,
        zooms,
        mesh_tiles_per_zoom,
        file_key,
    ) = args
    with open(filepath, "rb") as f:
        header = read_header(f)
        sb = step_bytes(header)
        total = (os.path.getsize(filepath) - header["body_offset"]) // sb
        for idx, time in time_index_range.items:
            timestep_data = read_timestep_at(f, header, sb, total, idx)
            for layer_name, value_keys in target_layers.items():
                subset_layer(
                    timestep_data, time, target_dir, zooms,
                    layer_name, value_keys, mesh_tiles_per_zoom,
                )
            advance_file_progress(file_key, 1)


def collect_files(sample_in: str | Path) -> list[Path]:
    root = Path(sample_in)
    return sorted(chain(root.rglob("*_surge_*.slf"), root.rglob("*_wave_*.slf")))


def _pretile_meshes(
    files: list[Path], target_zooms: dict[str, list[int]], sample_out: str | Path
) -> None:
    """location당 메쉬 타일을 sample_out/mesh/{location}/에 1벌만 미리 저장.

    SURGE/WAVE 메쉬가 동일하므로 model_type로 나누지 않는다. 육지 마스크용 SURGE 파일은
    같은 location의 surge 파일에서 가져온다(대표 파일도 가능하면 surge 우선).
    """
    surge_by_location: dict[str, Path] = {}
    rep_by_location: dict[str, Path] = {}
    for p in files:
        parts = parse_filename(p)
        if parts.model_type == "surge":
            surge_by_location.setdefault(parts.location, p)
        rep_by_location.setdefault(parts.location, p)
    for location, rep in rep_by_location.items():
        surge_file = surge_by_location.get(location)
        zooms = resolve_zooms(target_zooms, location)
        tile_mesh_for_group(surge_file or rep, surge_file, zooms, sample_out, location)


def start_subset(
    files: list[Path],
    sample_out: str | Path,
    target_zooms: dict[str, list[int]] = {
        "korea": [6],
        "default": [11],
    },
    layers: dict[str, dict[str, list[str]]] = DEFAULT_LAYERS,
    queue=None,
    file_callback: Callable[[Path], None] | None = None,
):
    """파일을 순차적으로 잡고, 각 파일의 hourly time index를 WORKERS개로 분할해 워커에 fan-out.

    완료된 파일 경로를 하나씩 yield. queue가 주어지면 워커가 진행 이벤트를 거기로 전송.
    """
    _pretile_meshes(files, target_zooms, sample_out)

    pool_kwargs = {}
    if queue is not None:
        pool_kwargs["initializer"] = init_worker
        pool_kwargs["initargs"] = (queue,)

    with Pool(WORKERS, **pool_kwargs) as pool:
        for filepath in files:
            filepath = Path(filepath)
            if file_callback is not None:
                file_callback(filepath)

            target_dir = _target_dir_for_file(filepath, sample_out)
            parts = parse_filename(filepath)
            target_layers = layers[parts.model_type]
            if _value_outputs_marked_complete(filepath, target_dir):
                yield filepath
                continue

            target_dir, target_layers, zooms, mesh_tiles_per_zoom, hourly = _prepare_file(
                filepath, target_zooms, sample_out, layers
            )
            if not hourly:
                _write_value_complete_marker(filepath, target_dir, target_layers)
                yield filepath
                continue

            pending = _filter_pending_indices(
                hourly,
                target_dir,
                target_layers,
                zooms,
                mesh_tiles_per_zoom,
            )
            if not pending:
                _write_value_complete_marker(filepath, target_dir, target_layers)
                yield filepath
                continue

            file_key = filepath.stem
            time_index_ranges = _split_time_index_ranges(pending, WORKERS)
            tasks = [
                (
                    filepath,
                    time_index_range,
                    target_dir,
                    target_layers,
                    zooms,
                    mesh_tiles_per_zoom,
                    file_key,
                )
                for time_index_range in time_index_ranges
            ]

            start_file_progress(queue, file_key, total=len(pending), desc=file_key)
            try:
                for _ in pool.imap_unordered(_process_time_index_range, tasks):
                    pass
            finally:
                end_file_progress(queue, file_key)

            _write_value_complete_marker(filepath, target_dir, target_layers)
            yield filepath
