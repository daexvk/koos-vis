import os
from pathlib import Path

import numpy as np


DIR_MODE = 0o755
FILE_MODE = 0o644


def _sudo_owner() -> tuple[int, int] | None:
    if os.geteuid() != 0:
        return None

    uid = os.getenv("SUDO_UID")
    gid = os.getenv("SUDO_GID")
    if uid is None or gid is None:
        return None

    return int(uid), int(gid)


def _make_accessible(path: str | Path, mode: int) -> None:
    owner = _sudo_owner()
    if owner is not None:
        os.chown(path, *owner)
    os.chmod(path, mode)


def ensure_dir(*parts: str | Path) -> str:
    path = os.path.join(*[str(p) for p in parts])
    target = Path(path)
    missing = []
    current = target
    while not current.exists():
        missing.append(current)
        current = current.parent

    os.makedirs(path, exist_ok=True)
    for directory in [target, *missing]:
        _make_accessible(directory, DIR_MODE)
    return path


def make_file_readable(path: str | Path) -> None:
    _make_accessible(path, FILE_MODE)


def write_mesh_tile_bin(path: str | Path, tile: dict) -> None:
    x = np.asarray(tile["x"], dtype=np.float32)
    y = np.asarray(tile["y"], dtype=np.float32)
    node = np.asarray(tile["node"], dtype=np.int32)
    conn = np.asarray(tile["conn"], dtype=np.int32).ravel()

    with open(path, "wb") as f:
        np.array([len(node), len(conn)], dtype=np.int32).tofile(f)
        x.tofile(f)
        y.tofile(f)
        node.tofile(f)
        conn.tofile(f)
    make_file_readable(path)


def write_mesh_index_npz(
    path: str | Path,
    tiles: dict[tuple[int, int], dict],
) -> None:
    tile_keys = sorted(tiles)
    tile_x = np.asarray([x for x, _ in tile_keys], dtype=np.int32)
    tile_y = np.asarray([y for _, y in tile_keys], dtype=np.int32)
    offsets = np.zeros(len(tile_keys) + 1, dtype=np.int64)
    node_parts = []

    for i, key in enumerate(tile_keys):
        node = np.asarray(tiles[key]["node"], dtype=np.int32)
        node_parts.append(node)
        offsets[i + 1] = offsets[i] + len(node)

    nodes = (
        np.concatenate(node_parts).astype(np.int32, copy=False)
        if node_parts
        else np.empty(0, dtype=np.int32)
    )

    path = Path(path)
    ensure_dir(path.parent)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "wb") as f:
        np.savez(f, tile_x=tile_x, tile_y=tile_y, offsets=offsets, nodes=nodes)
    make_file_readable(tmp_path)
    tmp_path.replace(path)
    make_file_readable(path)


def read_mesh_index_npz(path: str | Path) -> dict[tuple[int, int], dict]:
    with np.load(path) as data:
        tile_x = data["tile_x"]
        tile_y = data["tile_y"]
        offsets = data["offsets"]
        nodes = data["nodes"]

        tiles: dict[tuple[int, int], dict] = {}
        for i, (x, y) in enumerate(zip(tile_x, tile_y)):
            start = int(offsets[i])
            stop = int(offsets[i + 1])
            tiles[(int(x), int(y))] = {"node": nodes[start:stop].copy()}
        return tiles


def write_values_tile_bin(path: str | Path, tile: dict, value_keys: list[str]) -> None:
    node = np.asarray(tile["node"], dtype=np.int32)

    with open(path, "wb") as f:
        np.array([len(node)], dtype=np.int32).tofile(f)
        node.tofile(f)
        for k in value_keys:
            np.asarray(tile[k], dtype=np.float32).tofile(f)
    make_file_readable(path)
