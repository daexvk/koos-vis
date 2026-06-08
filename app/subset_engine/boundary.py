"""메쉬 연결성에서 도메인 경계를 닫힌 폴리곤으로 추출해 GeoJSON 마스크로 저장.

경계 edge = 정확히 한 삼각형에만 속하는 edge. 이 edge들을 내부가 좌측이 되도록
방향을 맞춰 닫힌 ring으로 잇고(외곽 CCW, 섬 CW), shell/hole로 조립해
Polygon/MultiPolygon을 만든다. 결과는 data/boundaries/{location}/boundary.geojson.

start_subset(_pretile_meshes)에서 location별로 write_boundary_geojson을 호출한다.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from shapely.geometry import MultiPolygon, Point, Polygon, mapping

from app.subset_engine.utils.file import ensure_dir, make_file_readable

BOUNDARY_GEOJSON_NAME = "boundary.geojson"


def _boundary_directed_edges(
    triangles: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """삼각형 (M,3)에서 boundary directed edge (u, v, w=제3정점)를 반환.

    무향 키(min,max) 다중도가 1인 edge만 골라, 원래 삼각형 winding 방향의
    directed edge (u->v)와 그 제3정점 w를 함께 돌려준다.
    """
    tri = np.asarray(triangles, dtype=np.int64)
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    u = np.concatenate([a, b, c])
    v = np.concatenate([b, c, a])
    w = np.concatenate([c, a, b])

    lo = np.minimum(u, v)
    hi = np.maximum(u, v)
    key = lo * (tri.max() + 1) + hi
    uniq, counts = np.unique(key, return_counts=True)
    boundary_keys = uniq[counts == 1]
    mask = np.isin(key, boundary_keys)
    return u[mask], v[mask], w[mask]


def _orient_interior_left(
    u: np.ndarray, v: np.ndarray, w: np.ndarray, x: np.ndarray, y: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """내부 정점 w가 directed edge u->v의 좌측에 오도록 방향을 정규화."""
    ux, uy = x[u], y[u]
    cross = (x[v] - ux) * (y[w] - uy) - (y[v] - uy) * (x[w] - ux)
    flip = cross < 0
    return np.where(flip, v, u), np.where(flip, u, v)


def _stitch_rings(su: np.ndarray, sv: np.ndarray) -> list[list[int]]:
    """directed edge(su->sv)들을 닫힌 ring(노드 인덱스 리스트)으로 잇는다."""
    next_node: dict[int, int] = {}
    dup = 0
    for s, t in zip(su.tolist(), sv.tolist()):
        if s in next_node:
            dup += 1
            continue
        next_node[s] = t
    if dup:
        print(f"[boundary] warning: {dup} nodes with >1 outgoing boundary edge")

    rings: list[list[int]] = []
    visited: set[int] = set()
    for start in list(next_node):
        if start in visited:
            continue
        ring = [start]
        visited.add(start)
        cur = next_node.get(start)
        while cur is not None and cur != start:
            if cur in visited:
                break
            visited.add(cur)
            ring.append(cur)
            cur = next_node.get(cur)
        if cur == start and len(ring) >= 3:
            rings.append(ring)
        else:
            print(f"[boundary] warning: dropped open/short ring of length {len(ring)}")
    return rings


def _signed_area(coords: np.ndarray) -> float:
    """shoelace 부호 면적(양수=CCW=shell, 음수=CW=hole)."""
    x, y = coords[:, 0], coords[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def compute_boundary_polygon(x: np.ndarray, y: np.ndarray, triangles: np.ndarray):
    """노드 좌표(lon/lat)와 삼각형(0-based)에서 경계 (Multi)Polygon을 만든다.

    반환: (geom, boundary_edge 수, ring 수).
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)

    u, v, w = _boundary_directed_edges(triangles)
    if len(u) == 0:
        raise ValueError("no boundary edges found")
    su, sv = _orient_interior_left(u, v, w, x, y)
    rings = _stitch_rings(su, sv)
    if not rings:
        raise ValueError("no closed boundary rings")

    shells: list[np.ndarray] = []
    holes: list[np.ndarray] = []
    for ring in rings:
        coords = np.column_stack([x[ring], y[ring]])
        (shells if _signed_area(coords) > 0 else holes).append(coords)

    shell_polys = [Polygon(c) for c in shells]
    hole_lists: list[list[np.ndarray]] = [[] for _ in shells]
    for h in holes:
        pt = Point(h[0])
        for i, sp in enumerate(shell_polys):
            if sp.contains(pt):
                hole_lists[i].append(h)
                break

    polys = [Polygon(shells[i], hole_lists[i]) for i in range(len(shells))]
    geom = polys[0] if len(polys) == 1 else MultiPolygon(polys)
    if not geom.is_valid:
        geom = geom.buffer(0)
    return geom, len(u), len(rings)


def _check_ipobo_consistency(
    triangles: np.ndarray, ipobo: np.ndarray, location: str
) -> None:
    """boundary edge 끝점 노드 == ipobo!=0 노드 인지 확인하고 불일치 시 경고."""
    u, v, _ = _boundary_directed_edges(triangles)
    edge_nodes = set(np.unique(np.concatenate([u, v])).tolist())
    ipobo_nodes = set(np.nonzero(np.asarray(ipobo) != 0)[0].tolist())
    if edge_nodes != ipobo_nodes:
        print(
            f"[boundary] {location}: ipobo mismatch — "
            f"edge_nodes={len(edge_nodes)} ipobo_nodes={len(ipobo_nodes)} "
            f"only_in_edges={len(edge_nodes - ipobo_nodes)} "
            f"only_in_ipobo={len(ipobo_nodes - edge_nodes)}"
        )


def write_boundary_geojson(
    rep_file: Path | str,
    location: str,
    boundaries_root: Path | str,
    force: bool = False,
) -> Path | None:
    """rep_file(SLF)에서 경계 마스크를 추출해 boundaries_root/boundary.geojson 저장.

    이미 파일이 있고 force=False면 건너뛰고 경로를 반환. 실패 시 예외를 전파한다.
    """
    from app.subset_engine.utils.parser import read_header

    out_path = Path(boundaries_root) / BOUNDARY_GEOJSON_NAME
    if out_path.exists() and not force:
        return out_path

    with open(rep_file, "rb") as f:
        header = read_header(f)
    x = np.asarray(header["x"])
    y = np.asarray(header["y"])
    triangles = header["ikle"].astype(np.int64) - 1

    _check_ipobo_consistency(triangles, header["ipobo"], location)
    geom, n_edges, n_rings = compute_boundary_polygon(x, y, triangles)

    feature = {
        "type": "Feature",
        "properties": {
            "location": location,
            "boundary_edges": int(n_edges),
            "rings": int(n_rings),
        },
        "geometry": mapping(geom),
    }
    payload = {"type": "FeatureCollection", "features": [feature]}

    ensure_dir(out_path.parent)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    make_file_readable(out_path)
    return out_path
