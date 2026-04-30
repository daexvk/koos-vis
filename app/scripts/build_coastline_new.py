from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import mercantile
from shapely.geometry import box, mapping
from shapely import make_valid


# z -> target vertex ratio (of original)
# z=6은 ZOOM_RATIOS에 포함하지 않음 — coastline_coarse.geojson을 그대로 사용
ZOOM_RATIOS = {
    8: 0.10,
    10: 0.55,
    12: 1
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=str(Path.home() / "data" / "coastline.json"),
        help="GeoJSON input path (z=8/10/12 source)",
    )
    parser.add_argument(
        "--coarse-input",
        default=None,
        help="Coarse GeoJSON input path for z=6 "
             "(default: sibling of --input named coastline_coarse.geojson)",
    )
    parser.add_argument(
        "--output",
        default=str(Path.home() / "data" / "coastline"),
        help="Output root for per-zoom simplified GeoJSON",
    )
    parser.add_argument(
        "--tile-output",
        default=str(Path.home() / "data" / "coastline_tiles"),
        help="Output root for slippy-map tile GeoJSON ({z}/{x}/{y}.geojson)",
    )
    return parser.parse_args()


def fix_geometry(geom):
    if geom is None or geom.is_empty:
        return None
    if not geom.is_valid:
        try:
            geom = make_valid(geom)
        except Exception:
            try:
                geom = geom.buffer(0)
            except Exception:
                return None
    if geom is None or geom.is_empty:
        return None
    return geom


def count_vertices(geom) -> int:
    if geom is None or geom.is_empty:
        return 0
    gt = geom.geom_type
    if gt == "Polygon":
        n = len(geom.exterior.coords)
        for ring in geom.interiors:
            n += len(ring.coords)
        return n
    if gt == "MultiPolygon":
        return sum(count_vertices(g) for g in geom.geoms)
    if gt == "LineString":
        return len(geom.coords)
    if gt == "MultiLineString":
        return sum(len(g.coords) for g in geom.geoms)
    if gt == "GeometryCollection":
        return sum(count_vertices(g) for g in geom.geoms)
    if gt == "Point":
        return 1
    if gt == "MultiPoint":
        return len(geom.geoms)
    return 0


def total_vertices(gdf: gpd.GeoDataFrame) -> int:
    return int(sum(count_vertices(g) for g in gdf.geometry))


def simplify_gdf(gdf: gpd.GeoDataFrame, tolerance: float) -> gpd.GeoDataFrame:
    if tolerance <= 0:
        return gdf.copy()
    out = gdf.copy()
    out.geometry = out.geometry.simplify(tolerance, preserve_topology=True)
    out = out[out.geometry.notnull() & ~out.geometry.is_empty].copy()
    return out


def find_tolerance_for_ratio(
    gdf: gpd.GeoDataFrame,
    original_count: int,
    target_ratio: float,
    tol_hi: float = 1.0,
    max_iter: int = 30,
    rel_eps: float = 0.01,
) -> tuple[float, gpd.GeoDataFrame, int]:
    """Binary search a Douglas-Peucker tolerance (in degrees) such that the
    resulting vertex count is roughly `target_ratio * original_count`."""
    target = target_ratio * original_count

    lo = 0.0
    hi = tol_hi
    # Grow hi until we reach or undershoot the target
    for _ in range(20):
        trial = simplify_gdf(gdf, hi)
        n = total_vertices(trial)
        if n <= target:
            break
        hi *= 2.0
    else:
        pass

    best_tol = hi
    best_gdf = trial
    best_n = n

    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        trial = simplify_gdf(gdf, mid)
        n = total_vertices(trial)

        if abs(n - target) < abs(best_n - target):
            best_tol = mid
            best_gdf = trial
            best_n = n

        if original_count > 0 and abs(n - target) / original_count < rel_eps:
            break

        if n > target:
            lo = mid
        else:
            hi = mid

    return best_tol, best_gdf, best_n


def write_geojson(gdf: gpd.GeoDataFrame, path: Path):
    features = []
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {},
                "geometry": mapping(geom),
            }
        )
    payload = {"type": "FeatureCollection", "features": features}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def load_and_normalize(input_path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(input_path)
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    fixed = [fix_geometry(g) for g in gdf.geometry]
    gdf = gdf.assign(geometry=fixed)
    gdf = gdf[gdf.geometry.notnull() & ~gdf.geometry.is_empty].copy()
    return gdf


def tile_polygon(z: int, x: int, y: int):
    b = mercantile.bounds(x, y, z)
    return box(b.west, b.south, b.east, b.north)


def build_tiles_for_zoom(
    gdf: gpd.GeoDataFrame,
    z: int,
    tile_output_root: Path,
) -> int:
    tile_buckets: dict[tuple[int, int], list] = defaultdict(list)

    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        minx, miny, maxx, maxy = geom.bounds
        for tile in mercantile.tiles(minx, miny, maxx, maxy, [z]):
            clip_box = tile_polygon(z, tile.x, tile.y)
            try:
                clipped = geom.intersection(clip_box)
            except Exception:
                fixed = fix_geometry(geom)
                if fixed is None:
                    continue
                try:
                    clipped = fixed.intersection(clip_box)
                except Exception:
                    continue

            if clipped.is_empty:
                continue

            clipped = fix_geometry(clipped)
            if clipped is None or clipped.is_empty:
                continue

            tile_buckets[(tile.x, tile.y)].append(
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": mapping(clipped),
                }
            )

    for (tx, ty), features in tile_buckets.items():
        tile_dir = tile_output_root / str(z) / str(tx)
        tile_dir.mkdir(parents=True, exist_ok=True)
        with open(tile_dir / f"{ty}.geojson", "w", encoding="utf-8") as f:
            json.dump(
                {"type": "FeatureCollection", "features": features},
                f,
                ensure_ascii=False,
            )

    return len(tile_buckets)


def main():
    args = parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_root = Path(args.output).expanduser().resolve()
    tile_output_root = Path(args.tile_output).expanduser().resolve()

    if args.coarse_input:
        coarse_input_path = Path(args.coarse_input).expanduser().resolve()
    else:
        coarse_input_path = input_path.parent / "coastline_coarse.geojson"

    if not input_path.exists():
        raise FileNotFoundError(f"input not found: {input_path}")
    if not coarse_input_path.exists():
        raise FileNotFoundError(f"coarse input not found: {coarse_input_path}")

    # --- z=6: coarse source, no DP simplification ---
    print(f"[z=6] reading coarse input: {coarse_input_path}")
    coarse_gdf = load_and_normalize(coarse_input_path)
    coarse_out = output_root / "6" / "coastline.geojson"
    write_geojson(coarse_gdf, coarse_out)
    print(f"[zoom 6] wrote {coarse_out} ({len(coarse_gdf)} features)")
    n_tiles = build_tiles_for_zoom(coarse_gdf, 6, tile_output_root)
    print(f"[zoom 6] wrote {n_tiles} tiles under {tile_output_root / '6'}")

    # --- z=8/10/12: DP simplification from fine input ---
    print(f"[z>=8] reading input: {input_path}")
    gdf = load_and_normalize(input_path)
    original_count = total_vertices(gdf)
    print(f"[z>=8] features: {len(gdf)}, vertices: {original_count}")

    for z, ratio in sorted(ZOOM_RATIOS.items()):
        if ratio >= 1.0:
            simplified = gdf
            tol = 0.0
            n = original_count
        else:
            tol, simplified, n = find_tolerance_for_ratio(
                gdf, original_count, ratio
            )

        pct = (n / original_count * 100.0) if original_count else 0.0
        print(
            f"[zoom {z}] target={ratio*100:.0f}% "
            f"tolerance={tol:.6g} vertices={n} ({pct:.2f}%)"
        )

        out_path = output_root / str(z) / "coastline.geojson"
        write_geojson(simplified, out_path)
        print(f"[zoom {z}] wrote {out_path}")

        n_tiles = build_tiles_for_zoom(simplified, z, tile_output_root)
        print(f"[zoom {z}] wrote {n_tiles} tiles under {tile_output_root / str(z)}")

    print("[done]")


if __name__ == "__main__":
    main()
