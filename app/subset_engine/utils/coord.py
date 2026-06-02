import math

import numpy as np


def latlon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    n = 1 << zoom
    lat_rad = math.radians(lat)
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


def latlon_to_tile_vec(
    lat: np.ndarray, lon: np.ndarray, zoom: int
) -> tuple[np.ndarray, np.ndarray]:
    n = 1 << zoom
    lat_rad = np.radians(lat)
    xtile = ((lon + 180.0) / 360.0 * n).astype(np.int64)
    ytile = ((1.0 - np.arcsinh(np.tan(lat_rad)) / np.pi) / 2.0 * n).astype(np.int64)
    return xtile, ytile
