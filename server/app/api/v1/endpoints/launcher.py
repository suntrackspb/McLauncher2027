from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.launcher import LauncherVersionOut, ServerProfileOut
from app.services import launcher_service, profile_service
from app.services.errors import ServiceError

router = APIRouter(prefix="/launcher", tags=["launcher"])


@router.get("/version", response_model=LauncherVersionOut)
async def version() -> LauncherVersionOut:
    """Последний релиз GitHub-репозитория сборки (см. LAUNCHER_GITHUB_REPO).
    Клиент сравнивает `version` (git tag) со своей вшитой версией и, если она
    новее, предлагает запустить отдельный updater-процесс (см. client/updater/)."""
    return await launcher_service.get_latest_version()


@router.get("/profile", response_model=ServerProfileOut)
async def profile(db: AsyncSession = Depends(get_db)) -> ServerProfileOut:
    """Профиль клиента (версия/loader/адрес сервера) — единственный источник
    правды вместо хардкода в client/ui_bridge/config.py. Клиент сравнивает его
    с локальным маркером установки и переустанавливает minecraft-директорию
    целиком, если что-то изменилось (см. DEV_PLAN.md)."""
    try:
        return await profile_service.get_profile(db)
    except ServiceError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
