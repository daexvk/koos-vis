from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse

from app.core.auth import verify_api_key
from app.services.cache_service import (
    get_flood_connectivity_path,
    get_flood_tile_path,
    read_flood_times,
)

router = APIRouter(prefix="/api", tags=["flood"])


@router.get("/flood/times")
def get_flood_times(
    _: None = Depends(verify_api_key),
):
    result = read_flood_times()
    if result is None:
        return JSONResponse(content={"time_indices": [], "times": []})
    return result


@router.get("/flood/{time_index}/conns/{z}")
def get_flood_connectivity(
    time_index: int,
    z: int,
    _: None = Depends(verify_api_key),
):
    path = get_flood_connectivity_path(time_index, z)

    if path is None:
        return JSONResponse(content={"triangles": []})

    return FileResponse(
        path=path,
        media_type="application/json",
        filename="connectivity.json",
    )


@router.get("/flood/conns/{z}")
def get_flood_connectivity_legacy(
    z: int,
    _: None = Depends(verify_api_key),
):
    return get_flood_connectivity(time_index=0, z=z, _=_)


@router.get("/flood/{time_index}/{z}/{x}/{y}")
def get_flood_tile(
    time_index: int,
    z: int,
    x: int,
    y: int,
    _: None = Depends(verify_api_key),
):
    path = get_flood_tile_path(time_index, z, x, y)

    if path is None:
        return JSONResponse(
            content={
                "z": z,
                "x": x,
                "y": y,
                "time_index": time_index,
                "points": [],
            }
        )

    return FileResponse(
        path=path,
        media_type="application/json",
        filename=f"{y}.json",
    )


@router.get("/flood/{z}/{x}/{y}")
def get_flood_tile_legacy(
    z: int,
    x: int,
    y: int,
    _: None = Depends(verify_api_key),
):
    return get_flood_tile(time_index=0, z=z, x=x, y=y, _=_)
