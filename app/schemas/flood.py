from typing import List

from pydantic import BaseModel


class FloodPoint(BaseModel):
    idx: int
    lat: float
    lon: float
    flood: float


class FloodTileResponse(BaseModel):
    z: int
    x: int
    y: int
    time_index: int
    points: List[FloodPoint]
