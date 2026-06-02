from __future__ import annotations

from pathlib import Path
import json
import os

APP_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(os.getenv("DATA_ROOT", str(APP_ROOT / "data")))
CACHE_ROOT = DATA_ROOT / "tiles"
SUBSET_INPUT_ROOT = Path(os.getenv("SUBSET_INPUT_ROOT", "/Volumes/T7/sample/NSTORM/DOUT"))
SUBSET_ROOT = Path(os.getenv("SUBSET_ROOT", str(DATA_ROOT / "subset")))
SUBSET_TRACK_ROOT = Path(
    os.getenv("SUBSET_TRACK_ROOT", str(SUBSET_INPUT_ROOT.parent / "DAIN" / "TRACK"))
)
COASTLINE_TILE_ROOT = DATA_ROOT / "coastline_tiles"
WEBP_ROOT = DATA_ROOT / "webp"
FLOOD_ROOT = DATA_ROOT / "flood_tiles"
UV_ROOT = DATA_ROOT / "tiles_uv"
WAVE_ROOT = DATA_ROOT / "wave_tiles"
FLOOD_TIME_ROOT = DATA_ROOT / "flood_tiles_time"
UV_TIME_ROOT = DATA_ROOT / "tiles_uv_time"
WAVE_TIME_ROOT = DATA_ROOT / "wave_tiles_time"
SUBSET_LAYER_LABELS = {
    "height": "수위",
    "tidal_height": "조위",
    "current": "해류",
    "wave": "파랑",
    "flood": "침수영역",
}
SUBSET_LAYER_MODEL_TYPES = {
    "height": "surge",
    "tidal_height": "surge",
    "current": "surge",
    "flood": "surge",
    "wave": "wave",
}
SUBSET_KOREA_ZOOM = 6
SUBSET_PORT_ZOOM = 11

def get_coastline_path():
    return DATA_ROOT / "coastline.json"
    # return None

def get_coastline_simplified_path(z: int):
    COASTLINE_SIMPLIFIED_ROOT = DATA_ROOT / "coastline"
    COASTLINE_SIMPLIFIED_ZOOMS = (6, 8, 10, 12)
    if z not in COASTLINE_SIMPLIFIED_ZOOMS:
        return None

    path = COASTLINE_SIMPLIFIED_ROOT / str(z) / "coastline.geojson"

    if not path.exists():
        return None

    return path


def get_coastline_tile_path(z: int, x: int, y: int):
    path = COASTLINE_TILE_ROOT / str(z) / str(x) / f"{y}.geojson"

    if not path.exists():
        return None

    return path

def get_webp_tile_path(z: int, x: int, y: int):
    path = WEBP_ROOT / str(z) / str(x) / f"{y}.webp"

    if not path.exists():
        return None

    return path

def read_tile(z: int, x: int, y: int):
    tile_path = CACHE_ROOT / str(z) / str(x) / f"{y}.json"

    if not tile_path.exists():
        return None

    with open(tile_path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_connectivity(z: int):
    conn_path = CACHE_ROOT / str(z) / "connectivity.json"

    if not conn_path.exists():
        return None

    with open(conn_path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_times(root: Path):
    path = root / "times.json"

    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _safe_path_part(value: str) -> str:
    if value in {"", ".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"invalid path part: {value!r}")
    return value


def get_subset_zoom_for_location(location: str):
    location = _safe_path_part(location)
    if location.casefold() == "korea":
        return SUBSET_KOREA_ZOOM

    return SUBSET_PORT_ZOOM


def get_subset_value_tile_path(
    typhoon_id: str,
    location: str,
    model_type: str,
    scenario_id: str,
    layer: str,
    time: str,
    z: int,
    x: int,
    y: int,
):
    path = (
        SUBSET_ROOT
        / _safe_path_part(typhoon_id)
        / _safe_path_part(location)
        / _safe_path_part(model_type)
        / _safe_path_part(scenario_id)
        / _safe_path_part(layer)
        / _safe_path_part(time)
        / str(z)
        / str(x)
        / f"{y}.bin"
    )

    if not path.exists():
        return None

    return path


def get_subset_model_type_for_layer(
    layer: str,
    typhoon_id: str | None = None,
    location: str | None = None,
    scenario_id: str | None = None,
):
    layer = _safe_path_part(layer)
    model_type = SUBSET_LAYER_MODEL_TYPES.get(layer)
    if model_type is not None:
        return model_type

    typhoon_ids = [typhoon_id] if typhoon_id is not None else _list_subset_dirs(SUBSET_ROOT)
    found: set[str] = set()
    for candidate_typhoon_id in typhoon_ids:
        if candidate_typhoon_id in {"mesh", "mesh_index"}:
            continue

        typhoon_dir = SUBSET_ROOT / _safe_path_part(candidate_typhoon_id)
        locations = [location] if location is not None else _list_subset_dirs(typhoon_dir)
        for candidate_location in locations:
            location_dir = typhoon_dir / _safe_path_part(candidate_location)
            for candidate_model_type in _list_subset_dirs(location_dir):
                model_dir = location_dir / candidate_model_type
                scenario_ids = [scenario_id] if scenario_id is not None else _list_subset_dirs(model_dir)
                for candidate_scenario_id in scenario_ids:
                    layer_dir = (
                        model_dir
                        / _safe_path_part(candidate_scenario_id)
                        / layer
                    )
                    if layer_dir.exists():
                        found.add(candidate_model_type)

    if len(found) == 1:
        return next(iter(found))

    if not found:
        return None

    raise ValueError(f"ambiguous subset layer: {layer!r}")


def get_subset_value_tile_path_by_layer(
    typhoon_id: str,
    location: str,
    scenario_id: str,
    layer: str,
    time: str,
    x: int,
    y: int,
):
    model_type = get_subset_model_type_for_layer(
        layer=layer,
        typhoon_id=typhoon_id,
        location=location,
        scenario_id=scenario_id,
    )
    if model_type is None:
        return None

    z = get_subset_zoom_for_location(location)
    return get_subset_value_tile_path(
        typhoon_id=typhoon_id,
        location=location,
        model_type=model_type,
        scenario_id=scenario_id,
        layer=layer,
        time=time,
        z=z,
        x=x,
        y=y,
    )


def get_subset_mesh_tile_path(
    model_type: str,
    location: str,
    z: int,
    x: int,
    y: int,
):
    path = (
        SUBSET_ROOT
        / "mesh"
        / _safe_path_part(model_type)
        / _safe_path_part(location)
        / str(z)
        / str(x)
        / f"{y}.bin"
    )

    if not path.exists():
        return None

    return path


def get_subset_mesh_tile_path_by_layer(
    layer: str,
    location: str,
    x: int,
    y: int,
):
    model_type = get_subset_model_type_for_layer(layer=layer, location=location)
    if model_type is None:
        return None

    z = get_subset_zoom_for_location(location)
    return get_subset_mesh_tile_path(
        model_type=model_type,
        location=location,
        z=z,
        x=x,
        y=y,
    )


def get_subset_mesh_index_path(
    model_type: str,
    location: str,
    z: int,
):
    path = (
        SUBSET_ROOT
        / "mesh_index"
        / _safe_path_part(model_type)
        / _safe_path_part(location)
        / f"{z}.npz"
    )

    if not path.exists():
        return None

    return path


def read_subset_tile_index(location: str):
    z = get_subset_zoom_for_location(location)
    model_type = None
    for candidate_model_type in _list_subset_dirs(SUBSET_ROOT / "mesh_index"):
        index_dir = (
            SUBSET_ROOT
            / "mesh_index"
            / _safe_path_part(candidate_model_type)
            / _safe_path_part(location)
        )
        if (index_dir / f"{z}.npz").exists():
            model_type = candidate_model_type
            break

    if model_type is None:
        return None

    index_dir = (
        SUBSET_ROOT
        / "mesh_index"
        / _safe_path_part(model_type)
        / _safe_path_part(location)
    )
    if not index_dir.exists():
        return None

    mesh_root = (
        SUBSET_ROOT
        / "mesh"
        / _safe_path_part(model_type)
        / _safe_path_part(location)
        / str(z)
    )
    if not mesh_root.exists():
        return None

    tiles = []
    for x_dir in sorted(p for p in mesh_root.iterdir() if p.is_dir()):
        if not x_dir.name.isdigit():
            continue

        for tile_path in sorted(x_dir.glob("*.bin")):
            if not tile_path.stem.isdigit():
                continue

            tiles.append(
                {
                    "z": z,
                    "x": int(x_dir.name),
                    "y": int(tile_path.stem),
                }
            )

    return {
        "location": location,
        "tiles": tiles,
    }


def _list_subset_dirs(path: Path):
    if not path.exists():
        return []

    return sorted(p.name for p in path.iterdir() if p.is_dir())


def read_subset_typhoon_names():
    names = {}
    if not SUBSET_TRACK_ROOT.exists():
        return names

    for path in sorted(SUBSET_TRACK_ROOT.glob("*.inp")):
        try:
            with open(path, "r", encoding="ascii", errors="replace") as f:
                first_line = f.readline().strip()
        except OSError:
            continue

        parts = first_line.split()
        if len(parts) < 2:
            continue

        case_id = parts[0]
        typhoon_name = parts[1]
        typhoon_id = case_id.split("_", 1)[0]
        if typhoon_id:
            names.setdefault(typhoon_id, typhoon_name)

    return names


def read_subset_catalog():
    metadata = read_subset_metadata(include_times=False, include_internal_model_type=False)
    typhoon_names = read_subset_typhoon_names()
    scenarios_by_typhoon = {}
    scenario_times = {}

    for combination in metadata["combinations"]:
        typhoon_id = combination["typhoon_id"]
        scenario_id = combination["scenario_id"]
        scenarios_by_typhoon.setdefault(typhoon_id, set()).add(scenario_id)
        scenario_key = (typhoon_id, scenario_id)
        scenario_time = {
            "typhoon_id": typhoon_id,
            "scenario_id": scenario_id,
            "time_count": combination["time_count"],
            "first_time": combination["first_time"],
            "last_time": combination["last_time"],
        }

        existing_scenario_time = scenario_times.get(scenario_key)
        if (
            existing_scenario_time is not None
            and (
                existing_scenario_time["time_count"] != scenario_time["time_count"]
                or existing_scenario_time["first_time"] != scenario_time["first_time"]
                or existing_scenario_time["last_time"] != scenario_time["last_time"]
            )
        ):
            raise ValueError(
                f"inconsistent times for typhoon/scenario: {typhoon_id}/{scenario_id}"
            )

        scenario_times[scenario_key] = scenario_time

    availability_map = {}
    for combination in metadata["combinations"]:
        key = (combination["typhoon_id"], combination["scenario_id"])
        item = availability_map.setdefault(
            key,
            {
                "typhoon_id": combination["typhoon_id"],
                "scenario_id": combination["scenario_id"],
                "locations": set(),
                "layers": set(),
                "layers_by_location": {},
            },
        )
        location = combination["location"]
        layer = combination["layer"]
        item["locations"].add(location)
        item["layers"].add(layer)
        item["layers_by_location"].setdefault(location, set()).add(layer)

    availability = []
    for item in availability_map.values():
        availability.append(
            {
                "typhoon_id": item["typhoon_id"],
                "scenario_id": item["scenario_id"],
                "locations": sorted(item["locations"]),
                "layers": sorted(item["layers"]),
                "layers_by_location": {
                    location: sorted(layers)
                    for location, layers in sorted(item["layers_by_location"].items())
                },
            }
        )

    return {
        "typhoons": [
            {
                "typhoon_id": typhoon_id,
                "typhoon_name": typhoon_names.get(typhoon_id),
                "scenario_ids": sorted(scenarios_by_typhoon.get(typhoon_id, set())),
            }
            for typhoon_id in metadata["typhoon_ids"]
        ],
        "locations": metadata["locations"],
        "variables": [
            {
                "layer": layer,
                "label": SUBSET_LAYER_LABELS.get(layer, layer),
            }
            for layer in metadata["layers"]
        ],
        "scenario_times": sorted(
            scenario_times.values(),
            key=lambda item: (item["typhoon_id"], item["scenario_id"]),
        ),
        "availability": sorted(
            availability,
            key=lambda item: (item["typhoon_id"], item["scenario_id"]),
        ),
    }


def read_subset_metadata(
    include_times: bool = False,
    include_internal_model_type: bool = True,
):
    typhoon_ids = _list_subset_dirs(SUBSET_ROOT)
    typhoon_ids = [
        typhoon_id
        for typhoon_id in typhoon_ids
        if typhoon_id not in {"mesh", "mesh_index"}
    ]

    locations: set[str] = set()
    model_types: set[str] = set()
    scenario_ids: set[str] = set()
    layers: set[str] = set()
    combinations = []
    tree = {}

    for typhoon_id in typhoon_ids:
        typhoon_dir = SUBSET_ROOT / typhoon_id
        typhoon_node = {}

        for location in _list_subset_dirs(typhoon_dir):
            locations.add(location)
            location_dir = typhoon_dir / location
            location_node = {}

            for model_type in _list_subset_dirs(location_dir):
                model_types.add(model_type)
                model_dir = location_dir / model_type
                model_node = {}

                for scenario_id in _list_subset_dirs(model_dir):
                    scenario_ids.add(scenario_id)
                    scenario_dir = model_dir / scenario_id
                    scenario_node = {}

                    for layer in _list_subset_dirs(scenario_dir):
                        layers.add(layer)
                        layer_dir = scenario_dir / layer
                        time_values = _list_subset_dirs(layer_dir)
                        layer_payload = {
                            "time_count": len(time_values),
                            "first_time": time_values[0] if time_values else None,
                            "last_time": time_values[-1] if time_values else None,
                        }
                        if include_times:
                            layer_payload["time_indices"] = list(range(len(time_values)))
                            layer_payload["times"] = [
                                {"time_index": i, "time_value": value}
                                for i, value in enumerate(time_values)
                            ]

                        scenario_node[layer] = layer_payload
                        combination = {
                            "typhoon_id": typhoon_id,
                            "location": location,
                            "scenario_id": scenario_id,
                            "layer": layer,
                            "time_count": len(time_values),
                            "first_time": time_values[0] if time_values else None,
                            "last_time": time_values[-1] if time_values else None,
                        }
                        if include_internal_model_type:
                            combination["model_type"] = model_type

                        combinations.append(combination)

                    model_node[scenario_id] = {
                        "layers": sorted(scenario_node.keys()),
                        "times_by_layer": scenario_node,
                    }

                location_node[model_type] = {
                    "scenario_ids": sorted(model_node.keys()),
                    "scenarios": model_node,
                }

            typhoon_node[location] = {
                "model_types": sorted(location_node.keys()),
                "models": location_node,
            }

        tree[typhoon_id] = {
            "locations": sorted(typhoon_node.keys()),
            "locations_detail": typhoon_node,
        }

    mesh = {}
    mesh_root = SUBSET_ROOT / "mesh"
    for model_type in _list_subset_dirs(mesh_root):
        model_mesh = {}
        for location in _list_subset_dirs(mesh_root / model_type):
            zooms = [
                int(value)
                for value in _list_subset_dirs(mesh_root / model_type / location)
                if value.isdigit()
            ]
            model_mesh[location] = {"zooms": sorted(zooms)}
        mesh[model_type] = model_mesh

    return {
        "typhoon_ids": typhoon_ids,
        "locations": sorted(locations),
        "model_types": sorted(model_types),
        "scenario_ids": sorted(scenario_ids),
        "layers": sorted(layers),
        "mesh": mesh,
        "tree": tree,
        "combinations": combinations,
    }


def read_subset_times(
    typhoon_id: str,
    location: str,
    model_type: str,
    scenario_id: str,
    layer: str,
):
    layer_dir = (
        SUBSET_ROOT
        / _safe_path_part(typhoon_id)
        / _safe_path_part(location)
        / _safe_path_part(model_type)
        / _safe_path_part(scenario_id)
        / _safe_path_part(layer)
    )

    if not layer_dir.exists():
        return None

    times = sorted(p.name for p in layer_dir.iterdir() if p.is_dir())
    return {
        "times": [
            {"time_index": i, "time_value": value}
            for i, value in enumerate(times)
        ],
        "time_indices": list(range(len(times))),
    }


def read_subset_times_by_layer(
    typhoon_id: str,
    location: str,
    scenario_id: str,
    layer: str,
):
    model_type = get_subset_model_type_for_layer(
        layer=layer,
        typhoon_id=typhoon_id,
        location=location,
        scenario_id=scenario_id,
    )
    if model_type is None:
        return None

    return read_subset_times(
        typhoon_id=typhoon_id,
        location=location,
        model_type=model_type,
        scenario_id=scenario_id,
        layer=layer,
    )


def get_time_tile_path(
    root: Path,
    time_index: int,
    z: int,
    x: int,
    y: int,
    legacy_time_index: int | None = None,
):
    path = root / f"t{time_index}" / str(z) / str(x) / f"{y}.json"

    if path.exists():
        return path

    # Backward compatibility for older one-time caches.
    if legacy_time_index is not None and time_index == legacy_time_index:
        legacy_path = root / str(z) / str(x) / f"{y}.json"
        if legacy_path.exists():
            return legacy_path

    return None


def get_time_connectivity_path(
    root: Path,
    time_index: int,
    z: int,
    legacy_time_index: int | None = None,
):
    path = root / f"t{time_index}" / str(z) / "connectivity.json"

    if path.exists():
        return path

    # Backward compatibility for older one-time caches.
    if legacy_time_index is not None and time_index == legacy_time_index:
        legacy_path = root / str(z) / "connectivity.json"
        if legacy_path.exists():
            return legacy_path

    return None


def read_uv_times():
    return read_times(UV_TIME_ROOT)


def read_wave_times():
    return read_times(WAVE_TIME_ROOT)


def read_flood_times():
    return read_times(FLOOD_TIME_ROOT)


def get_flood_tile_path(time_index: int, z: int, x: int, y: int):
    path = get_time_tile_path(FLOOD_TIME_ROOT, time_index, z, x, y)

    if path is None and time_index == 0:
        path = FLOOD_ROOT / str(z) / str(x) / f"{y}.json"
        if not path.exists():
            path = None

    if path is None:
        return None

    return path


def get_flood_connectivity_path(time_index: int, z: int):
    path = get_time_connectivity_path(FLOOD_TIME_ROOT, time_index, z)

    if path is None and time_index == 0:
        path = FLOOD_ROOT / str(z) / "connectivity.json"
        if not path.exists():
            path = None

    if path is None:
        return None

    return path


def get_uv_tile_path(time_index: int, z: int, x: int, y: int):
    path = get_time_tile_path(UV_TIME_ROOT, time_index, z, x, y)

    if path is None and time_index == 864:
        path = UV_ROOT / str(z) / str(x) / f"{y}.json"
        if not path.exists():
            path = None

    if path is None:
        return None

    return path


def get_uv_connectivity_path(time_index: int, z: int):
    path = get_time_connectivity_path(UV_TIME_ROOT, time_index, z)

    if path is None and time_index == 864:
        path = UV_ROOT / str(z) / "connectivity.json"
        if not path.exists():
            path = None

    if path is None:
        return None

    return path


def get_wave_tile_path(z: int, x: int, y: int):
    path = WAVE_ROOT / str(z) / str(x) / f"{y}.json"

    if not path.exists():
        return None

    return path


def get_wave_connectivity_path(z: int):
    path = WAVE_ROOT / str(z) / "connectivity.json"

    if not path.exists():
        return None

    return path
