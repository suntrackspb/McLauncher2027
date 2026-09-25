from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import crud_mod
from app.models.mod import Mod, ModType


async def get_required_mods(db: AsyncSession, loader: str, mc_version: str) -> list[Mod]:
    return await crud_mod.get_by_filter(
        db, mod_type=ModType.required, loader=loader, mc_version=mc_version
    )


async def get_optional_mods(db: AsyncSession, loader: str, mc_version: str) -> list[Mod]:
    return await crud_mod.get_by_filter(
        db, mod_type=ModType.optional, loader=loader, mc_version=mc_version
    )
