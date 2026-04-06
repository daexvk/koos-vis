from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree


def stride_coarsen_mesh(
    ikle2: np.ndarray,
    lon: np.ndarray,
    lat: np.ndarray,
    ipobo: np.ndarray,
    stride: int,
) -> tuple[np.ndarray, np.ndarray]:
    """ipobo==0인 interior 노드를 stride 간격으로 솎아내어 메쉬를 간소화한다.

    경계 노드(ipobo != 0)는 전부 보존하고, interior 노드는 매 stride번째만 보존.
    제거된 노드는 가장 가까운 보존 노드로 매핑하여 connectivity를 재구성한다.
    connectivity는 원본(보존 노드) 인덱스를 유지한다.

    Parameters
    ----------
    stride : int
        interior 노드를 몇 개 간격으로 보존할지. 예: stride=5이면 5개 중 1개만 보존.

    Returns
    -------
    keep_mask : 보존 여부 bool 배열 (원본 노드 수 길이)
    simplices : 재구성된 삼각형 (원본 인덱스)
    """
    n_nodes = len(ipobo)
    keep_mask = np.ones(n_nodes, dtype=bool)

    # interior 노드: stride 간격으로 솎아냄
    interior = np.where(ipobo == 0)[0]
    keep_mask[interior] = False
    keep_mask[interior[::stride]] = True

    # 제거된 노드 → 가장 가까운 보존 노드로 매핑
    keep_idx = np.where(keep_mask)[0]
    tree = cKDTree(np.column_stack([lon[keep_idx], lat[keep_idx]]))
    _, local_idx = tree.query(np.column_stack([lon, lat]))
    node_map = keep_idx[local_idx]  # 모든 원본 노드 → 보존 노드의 원본 인덱스

    # 원본 삼각형의 꼭짓점을 보존 노드로 매핑
    mapped = node_map[ikle2]
    valid = (
        (mapped[:, 0] != mapped[:, 1])
        & (mapped[:, 1] != mapped[:, 2])
        & (mapped[:, 0] != mapped[:, 2])
    )
    simplices = np.unique(np.sort(mapped[valid], axis=1), axis=0)

    return keep_mask, simplices


def subset_connectivity(
    ikle2: np.ndarray,
    node_mask: np.ndarray,
) -> np.ndarray:
    """꼭짓점이 node_mask에 속하는 삼각형을 반환한다. 인덱스는 원본 그대로."""
    has_target_node = node_mask[ikle2].all(axis=1)
    return ikle2[has_target_node]
