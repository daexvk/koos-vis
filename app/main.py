from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import coastline_router, flood_router, tile_router, uv_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # 모든 도메인 허용
    allow_credentials=True,
    allow_methods=["*"],            # GET, POST, PUT 등 모든 메서드 허용
    allow_headers=["*"],            # 모든 헤더 허용
)

app.include_router(flood_router.router)
app.include_router(uv_router.router)
app.include_router(coastline_router.router)
app.include_router(tile_router.router)
