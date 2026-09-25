from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mod import Mod, ModType


async def get_by_filter(
    db: AsyncSession, *, mod_type: ModType, loader: str, mc_version: str
) -> list[Mod]:
    result = await db.execute(
        select(Mod).where(
            Mod.mod_type == mod_type,
            Mod.loader == loader,
            Mod.mc_version == mc_version,
        )
    )
    return list(result.scalars().all())
