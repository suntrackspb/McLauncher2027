from fastapi import APIRouter

from app.schemas.launcher import LauncherVersionOut
from app.services import launcher_service

router = APIRouter(prefix="/launcher", tags=["launcher"])


@router.get("/version", response_model=LauncherVersionOut)
async def version() -> LauncherVersionOut:
    """Последний релиз GitHub-репозитория сборки (см. LAUNCHER_GITHUB_REPO).
    Клиент сравнивает `version` (git tag) со своей вшитой версией и, если она
    новее, предлагает запустить отдельный updater-процесс (см. client/updater/)."""
    return await launcher_service.get_latest_version()
