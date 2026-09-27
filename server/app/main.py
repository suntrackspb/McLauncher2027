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

_authlib_dir = Path(settings.authlib_storage_dir)
_authlib_dir.mkdir(parents=True, exist_ok=True)
app.mount("/authlib-files", StaticFiles(directory=_authlib_dir), name="authlib-files")

_admin_ui_dir = Path(__file__).resolve().parent / "static" / "admin"
app.mount("/admin", StaticFiles(directory=_admin_ui_dir, html=True), name="admin-ui")


@app.get("/health")
async def health():
    return {"status": "ok"}
