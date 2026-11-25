from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.launcher import AuthlibJarOut, LauncherVersionOut, ServerProfileOut
from app.services import authlib_service, launcher_service, profile_service
from app.services.errors import ServiceError

router = APIRouter(prefix="/launcher", tags=["launcher"])


@router.get("/version", response_model=LauncherVersionOut)
async def version() -> LauncherVersionOut:
    """Последний релиз GitHub-репозитория сборки (см. LAUNCHER_GITHUB_REPO).
    Клиент сравнивает `version` (git tag) со своей вшитой версией и, если она
    новее, предлагает запустить отдельный updater-процесс (см. client/updater/)."""
    return await launcher_service.get_latest_version()


@router.get("/profile", response_model=ServerProfileOut, response_model_exclude_defaults=True)
async def profile(
    db: AsyncSession = Depends(get_db), supports_client_zip: bool = False,
) -> ServerProfileOut:
    """Профиль установки и подключения клиента."""
    try:
        current = await profile_service.get_profile(db)
    except ServiceError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    if current.client_zip_url and not supports_client_zip:
        raise HTTPException(status_code=409, detail="Обновите лаунчер для установки сборки из ZIP")
    return ServerProfileOut.model_validate(current)


@router.get("/authlib-jars", response_model=list[AuthlibJarOut])
async def authlib_jars() -> list[AuthlibJarOut]:
    """Пропатченные authlib-jar'ы (для skin/join-редиректа на наш бэкенд) —
    кладутся руками в storage/authlib_dir при деплое (см. ops-чеклист в
    DEV_PLAN.md), не зашиты в сборку лаунчера. Клиент скачивает и кэширует
    нужную версию сам (см. core/launch/authlib_patch.py)."""
    return authlib_service.list_jars()
