from fastapi import APIRouter, HTTPException, Depends
from app.services.cache_service import read_tile, read_connectivity, get_webp_tile_path
from app.core.auth import verify_api_key
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api", tags=["tiles"])

@router.get("/map/{z}/{x}/{y}")
def get_map_webp(
    z: int,
    x: int,
    y: int,
    _: None = Depends(verify_api_key),
):
    path = get_webp_tile_path(z, x, y)

    if path is None:
        raise HTTPException(status_code=404, detail="map tile not found")

    return FileResponse(
        path=path,
        media_type="image/webp",
        filename=f"{y}.webp",
    )

@router.get("/conns/{z}")
def get_connectivity(
    z: int,
    _: None = Depends(verify_api_key),
):
    result = read_connectivity(z)

    if result is None:
        raise HTTPException(status_code=404, detail="connectivity not found")

    return result

@router.get("/{z}/{x}/{y}")
def get_tile(
    z: int,
    x: int,
    y: int,
    _: None = Depends(verify_api_key),
):
    result = read_tile(z, x, y)

    if result is None:
        raise HTTPException(status_code=404, detail="tile not found")

    return result
