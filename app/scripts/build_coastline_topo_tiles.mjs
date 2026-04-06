import fs from "fs";
import path from "path";
import { execFileSync } from "child_process";

const INPUT = "/home1/ncloud/data/water_polygons_clipped.json";
const OUTPUT_ROOT = "/home1/ncloud/data/coastline_tiles_topo";
const MIN_Z = 5;
const MAX_Z = 8;

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function lon2tileX(lon, z) {
  return Math.floor(((lon + 180) / 360) * Math.pow(2, z));
}

function lat2tileY(lat, z) {
  const clampedLat = clamp(lat, -85.05112878, 85.05112878);
  const rad = (clampedLat * Math.PI) / 180;
  return Math.floor(
    ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) *
      Math.pow(2, z)
  );
}

function tile2lon(x, z) {
  return (x / Math.pow(2, z)) * 360 - 180;
}

function tile2lat(y, z) {
  const n = Math.PI - (2 * Math.PI * y) / Math.pow(2, z);
  return (180 / Math.PI) * Math.atan(Math.sinh(n));
}

function tileBounds(z, x, y) {
  return {
    minLon: tile2lon(x, z),
    maxLon: tile2lon(x + 1, z),
    minLat: tile2lat(y + 1, z),
    maxLat: tile2lat(y, z),
  };
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function writeBboxGeoJSON(bboxPath, bounds) {
  const fc = {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: {},
        geometry: {
          type: "Polygon",
          coordinates: [[
            [bounds.minLon, bounds.minLat],
            [bounds.maxLon, bounds.minLat],
            [bounds.maxLon, bounds.maxLat],
            [bounds.minLon, bounds.maxLat],
            [bounds.minLon, bounds.minLat],
          ]],
        },
      },
    ],
  };

  fs.writeFileSync(bboxPath, JSON.stringify(fc));
}

function getInputBBox(inputPath) {
  const raw = fs.readFileSync(inputPath, "utf-8");
  const data = JSON.parse(raw);

  if (Array.isArray(data.bbox) && data.bbox.length === 4) {
    const [minLon, minLat, maxLon, maxLat] = data.bbox;
    return { minLon, minLat, maxLon, maxLat };
  }

  if (!data.transform || !Array.isArray(data.arcs)) {
    throw new Error(
      "Input TopoJSON must contain either bbox or both transform and arcs"
    );
  }

  const { scale, translate } = data.transform;

  if (
    !Array.isArray(scale) ||
    scale.length !== 2 ||
    !Array.isArray(translate) ||
    translate.length !== 2
  ) {
    throw new Error("Invalid TopoJSON transform");
  }

  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;

  for (const arc of data.arcs) {
    let x = 0;
    let y = 0;

    for (const point of arc) {
      x += point[0];
      y += point[1];

      const lon = translate[0] + x * scale[0];
      const lat = translate[1] + y * scale[1];

      if (lon < minLon) minLon = lon;
      if (lat < minLat) minLat = lat;
      if (lon > maxLon) maxLon = lon;
      if (lat > maxLat) maxLat = lat;
    }
  }

  if (
    !Number.isFinite(minLon) ||
    !Number.isFinite(minLat) ||
    !Number.isFinite(maxLon) ||
    !Number.isFinite(maxLat)
  ) {
    throw new Error("Failed to compute bbox from TopoJSON arcs");
  }

  return { minLon, minLat, maxLon, maxLat };
}

function getTileRangeForBBox(bbox, z) {
  const maxIndex = Math.pow(2, z) - 1;

  let minX = lon2tileX(bbox.minLon, z);
  let maxX = lon2tileX(bbox.maxLon, z);

  let minY = lat2tileY(bbox.maxLat, z);
  let maxY = lat2tileY(bbox.minLat, z);

  minX = clamp(minX, 0, maxIndex);
  maxX = clamp(maxX, 0, maxIndex);
  minY = clamp(minY, 0, maxIndex);
  maxY = clamp(maxY, 0, maxIndex);

  return {
    minX: Math.min(minX, maxX),
    maxX: Math.max(minX, maxX),
    minY: Math.min(minY, maxY),
    maxY: Math.max(minY, maxY),
  };
}

function isProbablyEmptyTopoJSON(filePath) {
  if (!fs.existsSync(filePath)) return true;

  try {
    const raw = fs.readFileSync(filePath, "utf-8").trim();
    if (!raw) return true;

    const json = JSON.parse(raw);

    if (!json.objects || Object.keys(json.objects).length === 0) {
      return true;
    }

    if (!Array.isArray(json.arcs) || json.arcs.length === 0) {
      return true;
    }

    return false;
  } catch {
    return true;
  }
}

function main() {
  ensureDir(OUTPUT_ROOT);

  const bbox = getInputBBox(INPUT);
  console.log("[input bbox]", bbox);

  for (let z = MIN_Z; z <= MAX_Z; z++) {
    const range = getTileRangeForBBox(bbox, z);

    console.log(
      `[zoom ${z}] x:${range.minX}..${range.maxX}, y:${range.minY}..${range.maxY}`
    );

    let written = 0;
    let skipped = 0;

    for (let x = range.minX; x <= range.maxX; x++) {
      for (let y = range.minY; y <= range.maxY; y++) {
        const bounds = tileBounds(z, x, y);
        const tileDir = path.join(OUTPUT_ROOT, String(z), String(x));
        const outPath = path.join(tileDir, `${y}.topojson`);
        const tmpBbox = path.join("/tmp", `bbox_${z}_${x}_${y}.geojson`);

        ensureDir(tileDir);
        writeBboxGeoJSON(tmpBbox, bounds);

        try {
          execFileSync(
            "npx",
            [
              "mapshaper",
              INPUT,
              "-clip",
              tmpBbox,
              "-o",
              "format=topojson",
              outPath,
            ],
            { stdio: "pipe" }
          );

          if (isProbablyEmptyTopoJSON(outPath)) {
            fs.rmSync(outPath, { force: true });
            skipped += 1;
          } else {
            written += 1;
          }
        } catch {
          fs.rmSync(outPath, { force: true });
          skipped += 1;
        } finally {
          fs.rmSync(tmpBbox, { force: true });
        }
      }
    }

    console.log(`[zoom ${z}] written=${written}, skipped=${skipped}`);
  }

  console.log("done");
}

main();