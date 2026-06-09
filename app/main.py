from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.routers import (
    coastline_router,
    subset_router,
    tile_router,
    timeseries_router,
)

# from app.routers import (
#     coastline_router,
#     flood_router,
#     subset_router,
#     tile_router,
#     uv_router,
#     wave_router,
# )

app = FastAPI()

app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # 모든 도메인 허용
    allow_credentials=True,
    allow_methods=["*"],            # GET, POST, PUT 등 모든 메서드 허용
    allow_headers=["*"],            # 모든 헤더 허용
)

app.include_router(subset_router.router)
app.include_router(coastline_router.router)
app.include_router(tile_router.router)
app.include_router(timeseries_router.router)
# app.include_router(flood_router.router)
# app.include_router(uv_router.router)
# app.include_router(wave_router.router)
