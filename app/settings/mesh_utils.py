from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree


def _median_edge_length(
    ikle2: np.ndarray, lon: np.ndarray, lat: np.ndarray,
    sample_size: int = 10_000,
) -> float:
    """메쉬 삼각형 변의 중앙값 길이를 추정한다."""
    sample = ikle2[: min(sample_size, len(ikle2))]
    edges = np.vstack([sample[:, [0, 1]], sample[:, [1, 2]], sample[:, [0, 2]]])
    dx = lon[edges[:, 0]] - lon[edges[:, 1]]
    dy = lat[edges[:, 0]] - lat[edges[:, 1]]
    return float(np.median(np.sqrt(dx ** 2 + dy ** 2)))


def coarsen_mesh(
    ikle2: np.ndarray,
    lon: np.ndarray,
    lat: np.ndarray,
    ipobo: np.ndarray,
    factor: float = 3.0,
) -> tuple[np.ndarray, np.ndarray]:
    """cKDTree 반경 기반으로 메쉬를 coarsen한다. 경계 노드는 전부 보존.

    Parameters
    ----------
    factor : float
        중앙값 edge 길이에 곱할 배수. 클수록 노드가 많이 줄어든다.

    Returns
    -------
    keep : 보존된 노드의 원본 인덱스 (정렬됨)
    simplices : coarsen된 삼각형 (keep 기준 인덱스)
    """
    min_dist = _median_edge_length(ikle2, lon, lat) * factor

    is_boundary = ipobo != 0
    boundary_idx = np.where(is_boundary)[0]
    interior_idx = np.where(~is_boundary)[0]

    # 경계 노드는 전부 보존
    keep_mask = is_boundary.copy()

    # 내부 노드: 반경 기반 greedy decimation
    if len(interior_idx) > 0:
        interior_pts = np.column_stack([lon[interior_idx], lat[interior_idx]])
        tree = cKDTree(interior_pts)

        visited = np.zeros(len(interior_idx), dtype=bool)
        for i in range(len(interior_idx)):
            if visited[i]:
                continue
            keep_mask[interior_idx[i]] = True
            neighbors = tree.query_ball_point(interior_pts[i], min_dist)
            for j in neighbors:
                visited[j] = True

    keep = np.where(keep_mask)[0]

    # 보존 노드로 connectivity 재구성
    kept_pts = np.column_stack([lon[keep], lat[keep]])
    tree = cKDTree(kept_pts)
    all_pts = np.column_stack([lon, lat])
    _, node_map = tree.query(all_pts)

    mapped = node_map[ikle2]
    valid = (
        (mapped[:, 0] != mapped[:, 1])
        & (mapped[:, 1] != mapped[:, 2])
        & (mapped[:, 0] != mapped[:, 2])
    )

    simplices = np.unique(np.sort(mapped[valid], axis=1), axis=0)

    return keep, simplices


def subset_connectivity(
    ikle2: np.ndarray,
    node_mask: np.ndarray,
) -> np.ndarray:
    """꼭짓점이 node_mask에 속하는 삼각형을 반환한다. 인덱스는 원본 그대로."""
    has_target_node = node_mask[ikle2].all(axis=1)
    return ikle2[has_target_node]
