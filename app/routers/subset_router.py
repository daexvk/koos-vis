from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.core.auth import verify_api_key
from app.schemas.subset import (
    SubsetCatalogResponse,
    SubsetRunRequest,
    SubsetRunStatusResponse,
    SubsetTileIndexResponse,
)
from app.schemas.time import TimeListResponse
from app.services.cache_service import (
    get_subset_mesh_tile_path_by_layer,
    get_subset_value_tile_path_by_layer,
    read_subset_catalog,
    read_subset_tile_index,
    read_subset_times_by_layer,
)
from app.services.subset_job_service import (
    get_subset_job_status,
    start_subset_job,
    stop_subset_job,
)

router = APIRouter(prefix="/api/subset", tags=["subset"])


def _file_response(path, y: int):
    if path is None:
        raise HTTPException(status_code=404, detail="subset tile not found")

    return FileResponse(
        path=path,
        media_type="application/octet-stream",
        filename=f"{y}.bin",
    )


@router.get("/catalog", response_model=SubsetCatalogResponse)
def get_subset_catalog(
    _: None = Depends(verify_api_key),
):
    return read_subset_catalog()


@router.post("/run", response_model=SubsetRunStatusResponse)
def run_subset(
    request: SubsetRunRequest | None = None,
    _: None = Depends(verify_api_key),
):
    if request is not None and request.force:
        raise HTTPException(
            status_code=400,
            detail="force rerun is not supported yet",
        )

    status, _started = start_subset_job()
    return status


@router.get("/run/status", response_model=SubsetRunStatusResponse)
def get_subset_run_status(
    _: None = Depends(verify_api_key),
):
    return get_subset_job_status()


@router.post("/run/stop", response_model=SubsetRunStatusResponse)
def stop_subset_run(
    _: None = Depends(verify_api_key),
):
    return stop_subset_job()


@router.get("/tiles/{location}", response_model=SubsetTileIndexResponse)
def get_subset_tiles(
    location: str,
    _: None = Depends(verify_api_key),
):
    try:
        result = read_subset_tile_index(location=location)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=404, detail="subset tile index not found")

    return result


@router.get(
    "/{typhoon_id}/{location}/{scenario_id}/{layer}/times",
    response_model=TimeListResponse,
)
def get_subset_times_by_layer(
    typhoon_id: str,
    location: str,
    scenario_id: str,
    layer: str,
    _: None = Depends(verify_api_key),
):
    try:
        result = read_subset_times_by_layer(
            typhoon_id=typhoon_id,
            location=location,
            scenario_id=scenario_id,
            layer=layer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result is None:
        return {"time_indices": [], "times": []}

    return result


@router.get(
    "/mesh/{location}/{layer}/{x}/{y}",
    response_class=FileResponse,
    responses={
        200: {
            "content": {"application/octet-stream": {}},
            "description": "Subset mesh tile binary. Uses z=6 for korea and z=11 for other locations.",
        }
    },
)
def get_subset_mesh_tile_by_layer(
    location: str,
    layer: str,
    x: int,
    y: int,
    _: None = Depends(verify_api_key),
):
    try:
        path = get_subset_mesh_tile_path_by_layer(
            layer=layer,
            location=location,
            x=x,
            y=y,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _file_response(path, y)


@router.get(
    "/{typhoon_id}/{location}/{scenario_id}/{layer}/{time}/{x}/{y}",
    response_class=FileResponse,
    responses={
        200: {
            "content": {"application/octet-stream": {}},
            "description": "Subset value tile binary. Uses z=6 for korea and z=11 for other locations.",
        }
    },
)
def get_subset_value_tile_by_layer(
    typhoon_id: str,
    location: str,
    scenario_id: str,
    layer: str,
    time: str,
    x: int,
    y: int,
    _: None = Depends(verify_api_key),
):
    try:
        path = get_subset_value_tile_path_by_layer(
            typhoon_id=typhoon_id,
            location=location,
            scenario_id=scenario_id,
            layer=layer,
            time=time,
            x=x,
            y=y,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _file_response(path, y)
