from typing import List

from pydantic import BaseModel


class WavePoint(BaseModel):
    idx: int
    lat: float
    lon: float
    deg: float
    height: float


class WaveTileResponse(BaseModel):
    z: int
    x: int
    y: int
    time_index: int
    points: List[WavePoint]
    connectivity: List[List[int]]


class WaveConnectivityResponse(BaseModel):
    connectivity: List[List[int]]
