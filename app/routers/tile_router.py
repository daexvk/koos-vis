from fastapi import APIRouter, HTTPException, Depends
from app.services.cache_service import read_tile
from app.core.auth import verify_api_key

router = APIRouter(prefix="/api", tags=["tiles"])


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