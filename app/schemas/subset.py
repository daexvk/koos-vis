from typing import Dict, List

from pydantic import BaseModel


class SubsetTyphoon(BaseModel):
    typhoon_id: str
    typhoon_name: str | None = None
    scenario_ids: List[str]


class SubsetVariable(BaseModel):
    layer: str
    label: str


class SubsetScenarioTime(BaseModel):
    typhoon_id: str
    scenario_id: str
    time_count: int
    first_time: str | None = None
    last_time: str | None = None


class SubsetAvailability(BaseModel):
    typhoon_id: str
    scenario_id: str
    locations: List[str]
    layers: List[str]
    layers_by_location: Dict[str, List[str]]


class SubsetCatalogResponse(BaseModel):
    typhoons: List[SubsetTyphoon]
    locations: List[str]
    variables: List[SubsetVariable]
    scenario_times: List[SubsetScenarioTime]
    availability: List[SubsetAvailability]


class SubsetTileIndexItem(BaseModel):
    z: int
    x: int
    y: int


class SubsetTileIndexResponse(BaseModel):
    location: str
    tiles: List[SubsetTileIndexItem]


class SubsetRunRequest(BaseModel):
    force: bool = False


class SubsetRunStatusResponse(BaseModel):
    job_id: str | None = None
    status: str
    pid: int | None = None
    input_root: str
    output_root: str
    total_files: int
    completed_files: int
    current_file: str | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
