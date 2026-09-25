from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.core import admin_auth
from app.core.config import settings


@asynccontextmanager
async def _lifespan(app: FastAPI):
    admin_auth.ensure_admin_credentials_ready()
    yield


app = FastAPI(title="McLauncher2027 backend", lifespan=_lifespan)
app.include_router(api_router, prefix="/api/v1")

_textures_dir = Path(settings.textures_storage_dir)
_textures_dir.mkdir(parents=True, exist_ok=True)
app.mount("/textures", StaticFiles(directory=_textures_dir), name="textures")

_mods_dir = Path(settings.mods_storage_dir)
_mods_dir.mkdir(parents=True, exist_ok=True)
app.mount("/mod-files", StaticFiles(directory=_mods_dir), name="mod-files")


@app.get("/health")
async def health():
    return {"status": "ok"}
