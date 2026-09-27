from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.server_profile import ServerProfile

_SINGLETON_ID = 1


async def get(db: AsyncSession) -> ServerProfile | None:
    result = await db.execute(select(ServerProfile).where(ServerProfile.id == _SINGLETON_ID))
    return result.scalar_one_or_none()


async def upsert(
    db: AsyncSession,
    *,
    mc_version: str,
    loader: str,
    loader_version: str | None,
    server_address: str,
    server_port: int,
) -> ServerProfile:
    profile = await get(db)
    if profile is None:
        profile = ServerProfile(id=_SINGLETON_ID)
        db.add(profile)

    profile.mc_version = mc_version
    profile.loader = loader
    profile.loader_version = loader_version
    profile.server_address = server_address
    profile.server_port = server_port

    await db.commit()
    await db.refresh(profile)
    return profile
