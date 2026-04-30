from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse

from app.core.auth import verify_api_key
from app.services.cache_service import (
    get_uv_connectivity_path,
    get_uv_tile_path,
    read_uv_times,
)

router = APIRouter(prefix="/api", tags=["uv"])


@router.get("/uv/times")
def get_uv_times(
    _: None = Depends(verify_api_key),
):
    result = read_uv_times()
    if result is None:
        return JSONResponse(content={"time_indices": [], "times": []})
    return result


@router.get("/uv/{time_index}/connectivity/{z}")
def get_uv_connectivity(
    time_index: int,
    z: int,
    _: None = Depends(verify_api_key),
):
    path = get_uv_connectivity_path(time_index, z)

    if path is None:
        return JSONResponse(content={"triangles": []})

    return FileResponse(
        path=path,
        media_type="application/json",
        filename="connectivity.json",
    )


@router.get("/uv/connectivity/{z}")
def get_uv_connectivity_legacy(
    z: int,
    _: None = Depends(verify_api_key),
):
    return get_uv_connectivity(time_index=864, z=z, _=_)


@router.get("/uv/{time_index}/{z}/{x}/{y}")
def get_uv_tile(
    time_index: int,
    z: int,
    x: int,
    y: int,
    _: None = Depends(verify_api_key),
):
    path = get_uv_tile_path(time_index, z, x, y)

    if path is None:
        return JSONResponse(
            content={
                "z": z,
                "x": x,
                "y": y,
                "time_index": time_index,
                "points": [],
                "triangles": [],
            }
        )

    return FileResponse(
        path=path,
        media_type="application/json",
        filename=f"{y}.json",
    )


@router.get("/uv/{z}/{x}/{y}")
def get_uv_tile_legacy(
    z: int,
    x: int,
    y: int,
    _: None = Depends(verify_api_key),
):
    return get_uv_tile(time_index=864, z=z, x=x, y=y, _=_)
