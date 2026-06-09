from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import verify_api_key
from app.schemas.timeseries import (
    StationSeriesResponse,
    TimeseriesCatalogResponse,
)
from app.services.timeseries_service import (
    read_station_series,
    read_timeseries_catalog,
)

router = APIRouter(prefix="/api/timeseries", tags=["timeseries"])


@router.get("/catalog", response_model=TimeseriesCatalogResponse)
def get_timeseries_catalog(
    _: None = Depends(verify_api_key),
):
    return read_timeseries_catalog()


@router.get(
    "/{region_key}/{typhoon_id}/{scenario_id}/{station}/{variable}",
    response_model=StationSeriesResponse,
)
def get_station_series(
    region_key: str,
    typhoon_id: str,
    scenario_id: str,
    station: str,
    variable: str,
    _: None = Depends(verify_api_key),
):
    try:
        result = read_station_series(
            region_key=region_key,
            typhoon_id=typhoon_id,
            scenario_id=scenario_id,
            station=station,
            variable=variable,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=404, detail="timeseries not found")

    return {
        "region_key": region_key,
        "typhoon_id": typhoon_id,
        "scenario_id": scenario_id,
        "station": station,
        **result,
    }
