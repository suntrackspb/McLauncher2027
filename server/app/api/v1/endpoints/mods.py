from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.schemas.mod import ModOut
from app.services import mod_service

router = APIRouter(prefix="/mods", tags=["mods"])


@router.get("/manifest", response_model=list[ModOut])
async def manifest(
    loader: str = settings.default_loader,
    mc_version: str = settings.default_mc_version,
    db: AsyncSession = Depends(get_db),
):
    """Обязательные моды — клиент сверяет с локальной папкой mods/ и
    докачивает/удаляет расхождения."""
    return await mod_service.get_required_mods(db, loader, mc_version)


@router.get("/optional", response_model=list[ModOut])
async def optional(
    loader: str = settings.default_loader,
    mc_version: str = settings.default_mc_version,
    db: AsyncSession = Depends(get_db),
):
    """Каталог опциональных модов. Какие из них включены — решает и хранит клиент
    локально, сервер это не отслеживает (см. DEV_PLAN.md)."""
    return await mod_service.get_optional_mods(db, loader, mc_version)
