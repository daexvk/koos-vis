from typing import List

from pydantic import BaseModel


class UvPoint(BaseModel):
    idx: int
    lat: float
    lon: float
    u: float
    v: float


class UvTileResponse(BaseModel):
    z: int
    x: int
    y: int
    time_index: int
    points: List[UvPoint]
    triangles: List[List[int]]
