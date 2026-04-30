from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.core.auth import verify_api_key
from app.schemas.coastline import FeatureCollectionResponse
from app.services.cache_service import (
    get_coastline_path,
    get_coastline_simplified_path,
    get_coastline_tile_path,
)

router = APIRouter(prefix="/api", tags=["coastline"])


@router.get(
    "/coastline",
    response_class=FileResponse,
    responses={200: {"model": FeatureCollectionResponse}},
)
def get_coastline(
    _: None = Depends(verify_api_key),
):
    path = get_coastline_path()

    if path is None:
        raise HTTPException(status_code=404, detail="coastline not found")

    return FileResponse(
        path=path,
        media_type="application/json",
        filename="coastline.json",
    )


@router.get(
    "/coastline/{z}",
    response_class=FileResponse,
    responses={200: {"model": FeatureCollectionResponse}},
)
def get_coastline_by_zoom(
    z: int,
    _: None = Depends(verify_api_key),
):
    path = get_coastline_simplified_path(z)

    if path is None:
        raise HTTPException(status_code=404, detail="coastline not found")

    return FileResponse(
        path=str(path),
        media_type="application/json",
        filename=f"coastline_{z}.geojson",
    )


@router.get(
    "/coastline/{z}/{x}/{y}",
    response_class=FileResponse,
    responses={200: {"model": FeatureCollectionResponse}},
)
def get_coastline_tile(
    z: int,
    x: int,
    y: int,
    _: None = Depends(verify_api_key),
):
    path = get_coastline_tile_path(z, x, y)

    if path is None:
        return JSONResponse(
            status_code=200,
            content={
                "type": "FeatureCollection",
                "features": [],
            },
        )

    return FileResponse(
        path=str(path),
        media_type="application/json",
        filename=f"{z}_{x}_{y}.geojson",
    )
