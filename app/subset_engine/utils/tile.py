import numpy as np

from app.subset_engine.utils.coord import latlon_to_tile_vec


def bucket_mesh_by_tile(
    x: np.ndarray,
    y: np.ndarray,
    triangles: np.ndarray,
    zoom: int,
    land_mask: np.ndarray | None = None,
) -> dict[tuple[int, int], dict]:
    """노드와 삼각형을 타일 단위로 그룹핑. value 배열과 무관하게 메쉬만 다룸.

    Invariants:
      - 노드는 자기 좌표가 떨어지는 타일 하나에만 속함.
      - 삼각형은 세 정점이 떨어지는 모든 타일의 conn에 들어감.
      - node/conn 모두 global node index (원본 x/y 배열의 인덱스).

    land_mask가 주어지면(노드별 bool, 길이 npoin) 각 타일에 육지 노드(global index)를
    land_nodes로 담는다.
    """
    x = np.asarray(x)
    y = np.asarray(y)
    triangles = np.asarray(triangles, dtype=np.int64)
    land_mask_array = None if land_mask is None else np.asarray(land_mask)

    # 각 노드가 어느 타일에 속하는지 계산. (tx, ty)를 한 개의 정수 키로 인코딩.
    n = 1 << zoom
    node_tx, node_ty = latlon_to_tile_vec(y, x, zoom)
    node_tile_key = node_tx * n + node_ty

    # 1) 노드 그룹핑: 같은 타일 키를 가진 노드 인덱스들을 모아 타일별 dict 생성.
    tiles: dict[tuple[int, int], dict] = {}
    empty_conn = np.empty((0, 3), dtype=triangles.dtype)
    for key, node_idx in _group_indices_by_key(node_tile_key):
        tx, ty = divmod(int(key), n)
        tiles[(tx, ty)] = {
            "x": x[node_idx],
            "y": y[node_idx],
            "node": node_idx,
            "conn": empty_conn,
            "land_nodes": (
                node_idx[land_mask_array[node_idx]]
                if land_mask_array is not None
                else np.empty(0, dtype=node_idx.dtype)
            ),
        }

    # 2) 삼각형 그룹핑: 한 삼각형이 K개 타일에 걸치면 K개 타일 모두의 conn에 포함.
    #    한 삼각형의 세 정점이 같은 타일을 가리킬 수 있으므로 (tile_key, tri_id)를 dedupe.
    tri_id = np.repeat(np.arange(len(triangles), dtype=np.int64), 3)
    tri_tile_key = node_tile_key[triangles].ravel()
    pairs = np.unique(np.stack([tri_tile_key, tri_id], axis=1), axis=0)
    keys_per_pair, tris_per_pair = pairs[:, 0], pairs[:, 1]

    # np.unique는 lexsort된 결과를 주므로 같은 tile_key끼리 인접. 경계만 잡아 conn에 할당.
    group_starts = np.r_[0, np.where(np.diff(keys_per_pair) != 0)[0] + 1]
    group_ends = np.r_[group_starts[1:], len(keys_per_pair)]
    for s, e in zip(group_starts, group_ends):
        tx, ty = divmod(int(keys_per_pair[s]), n)
        tiles[(tx, ty)]["conn"] = triangles[tris_per_pair[s:e]]

    return tiles


def _group_indices_by_key(keys: np.ndarray):
    """정수 키 배열에 대해 (unique_key, 원본_인덱스_배열) 쌍을 yield."""
    order = np.argsort(keys, kind="stable")
    sorted_keys = keys[order]
    boundary = np.r_[True, sorted_keys[1:] != sorted_keys[:-1]]
    starts = np.where(boundary)[0]
    ends = np.r_[starts[1:], len(sorted_keys)]
    for s, e in zip(starts, ends):
        yield sorted_keys[s], order[s:e]


def bucket_values_by_tile(
    ds: dict, mesh_tiles: dict[tuple[int, int], dict], value_keys: list[str]
) -> dict[tuple[int, int], dict]:
    """미리 만들어둔 mesh_tiles의 node 인덱스를 그대로 써서 값 배열만 슬라이스."""
    value_arrays = {k: np.asarray(ds[k]) for k in value_keys} # key1: [0, 0, 0, 0, 0 ...], key2: ...
    out: dict[tuple[int, int], dict] = {} # {(8, 9): { key1: [0, 0, 0, ...], key2: ...}, (9, 10): {...} }
    for tkey, mtile in mesh_tiles.items():
        idx = mtile["node"]
        tile = {"node": idx}
        for k in value_keys:
            tile[k] = value_arrays[k][idx]
        out[tkey] = tile
    return out
