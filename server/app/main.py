from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.core.config import settings

app = FastAPI(title="McLauncher2027 backend")
app.include_router(api_router, prefix="/api/v1")

_textures_dir = Path(settings.textures_storage_dir)
_textures_dir.mkdir(parents=True, exist_ok=True)
app.mount("/textures", StaticFiles(directory=_textures_dir), name="textures")


@app.get("/health")
async def health():
    return {"status": "ok"}
