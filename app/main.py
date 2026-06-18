from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope
from app.routers import (
    coastline_router,
    subset_router,
    tile_router,
    timeseries_router,
)
from app.core.config import get_settings


class SpaStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        if response.status_code == 404 and scope["method"] in ("GET", "HEAD"):
            return await super().get_response("index.html", scope)
        return response

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


@app.get("/", include_in_schema=False)
def redirect_to_frontend():
    return RedirectResponse(url="/koos/")


app.mount(
    "/koos",
    SpaStaticFiles(directory=get_settings().paths.static_root, html=True),
    name="koos-static",
)
