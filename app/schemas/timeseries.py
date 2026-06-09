from typing import List

from pydantic import BaseModel

from app.schemas.subset import SubsetTyphoon


class TimeseriesStation(BaseModel):
    id: str
    lat: float
    lon: float


class TimeseriesVariable(BaseModel):
    id: str
    model: str
    variable: str
    label: str


class TimeseriesRegion(BaseModel):
    region: str
    region_key: str
    label: str
    typhoons: List[SubsetTyphoon]
    stations: List[TimeseriesStation]
    variables: List[TimeseriesVariable]


class TimeseriesCatalogResponse(BaseModel):
    regions: List[TimeseriesRegion]


class TimeseriesPoint(BaseModel):
    t: str
    value: float | None = None


class StationSeriesResponse(BaseModel):
    region_key: str
    typhoon_id: str
    scenario_id: str
    station: str
    variable: str
    model: str
    label: str
    points: List[TimeseriesPoint]
