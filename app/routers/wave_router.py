from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse

from app.core.auth import verify_api_key
from app.schemas.wave import WaveConnectivityResponse, WaveTileResponse
from app.services.cache_service import (
    get_wave_connectivity_path,
    get_wave_tile_path,
)

router = APIRouter(prefix="/api", tags=["wave"])


# @router.get("/wave/times", response_model=TimeListResponse)
# def get_wave_times(
#     _: None = Depends(verify_api_key),
# ):
#     result = read_wave_times()
#     if result is None:
#         return {"time_indices": [], "times": []}
#     return result


@router.get(
    "/wave/connectivity/{z}",
    response_class=FileResponse,
    responses={200: {"model": WaveConnectivityResponse}},
)
def get_wave_connectivity(
    z: int,
    _: None = Depends(verify_api_key),
):
    path = get_wave_connectivity_path(z)

    if path is None:
        return JSONResponse(content={"connectivity": []})

    return FileResponse(
        path=path,
        media_type="application/json",
        filename="connectivity.json",
    )


@router.get(
    "/wave/{z}/{x}/{y}",
    response_class=FileResponse,
    responses={200: {"model": WaveTileResponse}},
)
def get_wave_tile(
    z: int,
    x: int,
    y: int,
    _: None = Depends(verify_api_key),
):
    path = get_wave_tile_path(z, x, y)

    if path is None:
        return JSONResponse(
            content={
                "z": z,
                "x": x,
                "y": y,
                "time_index": 0,
                "points": [],
                "connectivity": [],
            }
        )

    return FileResponse(
        path=path,
        media_type="application/json",
        filename=f"{y}.json",
    )
