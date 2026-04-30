from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, mapping
from shapely.ops import linemerge


GRID = 1.0  # degrees
EPS = 1e-6  # tolerance for "on grid" / "axis aligned"


def on_grid(v: float) -> bool:
    return abs(v - round(v / GRID) * GRID) < EPS


def ring_to_segments(coords):
    for i in range(len(coords) - 1):
        yield coords[i], coords[i + 1]


def is_artifact(p1, p2) -> bool:
    x1, y1 = p1[0], p1[1]
    x2, y2 = p2[0], p2[1]
    dx = x2 - x1
    dy = y2 - y1
    if abs(dx) < EPS and on_grid(x1) and on_grid(x2):
        return True
    if abs(dy) < EPS and on_grid(y1) and on_grid(y2):
        return True
    return False


def clean_ring(coords):
    """Walk the ring; emit runs of non-artifact segments as LineStrings."""
    runs = []
    current = []
    for p1, p2 in ring_to_segments(coords):
        if is_artifact(p1, p2):
            if current:
                current.append(p1)
                if len(current) >= 2:
                    runs.append(current)
                current = []
        else:
            if not current:
                current.append(p1)
            current.append(p2)
    if len(current) >= 2:
        runs.append(current)
    return runs


def extract_lines(geom):
    lines = []
    gt = geom.geom_type
    if gt == "Polygon":
        rings = [list(geom.exterior.coords)] + [list(r.coords) for r in geom.interiors]
        for r in rings:
            lines.extend(clean_ring(r))
    elif gt == "MultiPolygon":
        for g in geom.geoms:
            lines.extend(extract_lines(g))
    elif gt == "LineString":
        lines.extend(clean_ring(list(geom.coords)))
    elif gt == "MultiLineString":
        for g in geom.geoms:
            lines.extend(clean_ring(list(g.coords)))
    return lines


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default=str(Path.home() / "data" / "coastline.json"))
    p.add_argument(
        "--output", default=str(Path.home() / "data" / "coastline_clean.geojson")
    )
    return p.parse_args()


def main():
    args = parse_args()
    inp = Path(args.input).expanduser().resolve()
    out = Path(args.output).expanduser().resolve()

    print(f"[1/3] reading {inp}")
    gdf = gpd.read_file(inp)
    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)

    print(f"[2/3] features={len(gdf)}, extracting non-grid segments...")
    all_lines = []
    for g in gdf.geometry:
        if g is None or g.is_empty:
            continue
        for run in extract_lines(g):
            all_lines.append(LineString(run))

    print(f"  raw line runs: {len(all_lines)}")
    merged = linemerge(MultiLineString(all_lines)) if all_lines else None
    if merged is None or merged.is_empty:
        features = []
    elif merged.geom_type == "LineString":
        features = [{"type": "Feature", "properties": {}, "geometry": mapping(merged)}]
    else:
        features = [
            {"type": "Feature", "properties": {}, "geometry": mapping(g)}
            for g in merged.geoms
        ]
    print(f"  merged features: {len(features)}")

    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"type": "FeatureCollection", "features": features}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f"[3/3] wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
