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


async def get_all(db: AsyncSession) -> list[Mod]:
    result = await db.execute(select(Mod).order_by(Mod.id))
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, mod_id: int) -> Mod | None:
    result = await db.execute(select(Mod).where(Mod.id == mod_id))
    return result.scalar_one_or_none()


async def create(
    db: AsyncSession,
    *,
    name: str,
    description: str | None,
    file_name: str,
    url: str,
    file_hash: str,
    size: int,
    mod_type: ModType,
    loader: str,
    mc_version: str,
) -> Mod:
    mod = Mod(
        name=name,
        description=description,
        file_name=file_name,
        url=url,
        file_hash=file_hash,
        size=size,
        mod_type=mod_type,
        loader=loader,
        mc_version=mc_version,
    )
    db.add(mod)
    await db.commit()
    await db.refresh(mod)
    return mod


async def delete(db: AsyncSession, mod: Mod) -> None:
    await db.delete(mod)
    await db.commit()
