from fastapi import APIRouter, HTTPException, Depends
from app.services.cache_service import read_tile, read_connectivity, get_coastline_path, get_coastline_topo_path, get_webp_tile_path
from app.core.auth import verify_api_key
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter(prefix="/api", tags=["tiles"])

@router.get("/coastline")
def get_coastline(
    _: None = Depends(verify_api_key),
):
    # 현재 임시로 None처리해뒀음. subsetting을 위함.
    path = get_coastline_path()

    if path is None:
        raise HTTPException(status_code=404, detail="coastline not found")

    return FileResponse(
        path=path,
        media_type="application/json",
        filename="coastline.json",
    )

@router.get("/coastline/{z}/{x}/{y}")
def get_coastline(
    z: int,
    x: int,
    y: int,
    _: None = Depends(verify_api_key),
):
    path = get_coastline_topo_path(z, x, y)

    if path is None:
        return JSONResponse(
            status_code=200,
            content={
                "type": "Topology",
                "objects": {},
                "arcs": [],
            },
        )

    return FileResponse(
        path=str(path),
        media_type="application/json",
        filename=f"{z}_{x}_{y}.topojson",
    )

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
    _: None = Depends(verify_api_key),  # 👈 여기만 추가
):
    result = read_tile(z, x, y)

    if result is None:
        raise HTTPException(status_code=404, detail="tile not found")

    return result