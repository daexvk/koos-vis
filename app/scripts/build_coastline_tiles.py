from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import mercantile
from shapely.geometry import box, mapping
from shapely import make_valid


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="GeoJSON input path")
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[2] / "data" / "coastline_tiles"),
        help="Output root directory",
    )
    parser.add_argument("--min-z", type=int, default=5)
    parser.add_argument("--max-z", type=int, default=8)
    parser.add_argument("--keep-properties", action="store_true")
    return parser.parse_args()


def tile_polygon(z: int, x: int, y: int):
    bounds = mercantile.bounds(x, y, z)
    return box(bounds.west, bounds.south, bounds.east, bounds.north)


def fix_geometry(geom):
    if geom is None or geom.is_empty:
        return None

    try:
        if not geom.is_valid:
            geom = make_valid(geom)
    except Exception:
        try:
            geom = geom.buffer(0)
        except Exception:
            return None

    if geom is None or geom.is_empty:
        return None

    # make_valid 후 GeometryCollection 나올 수 있어서
    # polygon 계열만 남기기
    if geom.geom_type == "GeometryCollection":
        polys = [
            g for g in geom.geoms
            if g.geom_type in ("Polygon", "MultiPolygon")
            and not g.is_empty
        ]
        if not polys:
            return None

        if len(polys) == 1:
            geom = polys[0]
        else:
            from shapely.geometry import MultiPolygon
            merged = []
            for g in polys:
                if g.geom_type == "Polygon":
                    merged.append(g)
                elif g.geom_type == "MultiPolygon":
                    merged.extend(list(g.geoms))
            geom = MultiPolygon(merged) if merged else None

    if geom is None or geom.is_empty:
        return None

    return geom


def normalize_gdf(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    gdf = gdf[gdf.geometry.notnull()].copy()
    gdf = gdf[~gdf.geometry.is_empty].copy()

    fixed_geometries = []
    keep_rows = []

    for idx, row in gdf.iterrows():
        fixed = fix_geometry(row.geometry)
        if fixed is None or fixed.is_empty:
            continue
        fixed_geometries.append(fixed)
        keep_rows.append(idx)

    gdf = gdf.loc[keep_rows].copy()
    gdf.geometry = fixed_geometries
    gdf = gdf.explode(index_parts=False, ignore_index=True)

    return gdf


def safe_properties(row, keep_properties: bool) -> dict:
    if not keep_properties:
        return {}

    props = {}
    for key, value in row.items():
        if key == "geometry":
            continue
        if hasattr(value, "item"):
            value = value.item()
        props[key] = value
    return props


def build_tiles(
    input_path: Path,
    output_root: Path,
    min_z: int,
    max_z: int,
    keep_properties: bool,
):
    print(f"[1/3] reading input: {input_path}")
    gdf = gpd.read_file(input_path)
    gdf = normalize_gdf(gdf)

    print(f"[2/3] features loaded: {len(gdf)}")
    output_root.mkdir(parents=True, exist_ok=True)

    for z in range(min_z, max_z + 1):
        print(f"[zoom {z}] processing...")
        tile_buckets = defaultdict(list)

        for _, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue

            minx, miny, maxx, maxy = geom.bounds
            props = safe_properties(row, keep_properties)

            for tile in mercantile.tiles(minx, miny, maxx, maxy, [z]):
                clip_box = tile_polygon(z, tile.x, tile.y)

                try:
                    clipped = geom.intersection(clip_box)
                except Exception:
                    fixed_geom = fix_geometry(geom)
                    if fixed_geom is None:
                        continue
                    try:
                        clipped = fixed_geom.intersection(clip_box)
                    except Exception:
                        continue

                if clipped.is_empty:
                    continue

                clipped = fix_geometry(clipped)
                if clipped is None or clipped.is_empty:
                    continue

                tile_buckets[(z, tile.x, tile.y)].append(
                    {
                        "type": "Feature",
                        "properties": props,
                        "geometry": mapping(clipped),
                    }
                )

        print(f"[zoom {z}] writing {len(tile_buckets)} tiles...")
        for (tz, tx, ty), features in tile_buckets.items():
            tile_dir = output_root / str(tz) / str(tx)
            tile_dir.mkdir(parents=True, exist_ok=True)

            tile_path = tile_dir / f"{ty}.geojson"
            payload = {
                "type": "FeatureCollection",
                "features": features,
            }

            with open(tile_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)

    print("[3/3] done")


def main():
    args = parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_root = Path(args.output).expanduser().resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"input not found: {input_path}")

    build_tiles(
        input_path=input_path,
        output_root=output_root,
        min_z=args.min_z,
        max_z=args.max_z,
        keep_properties=args.keep_properties,
    )


if __name__ == "__main__":
    main()
