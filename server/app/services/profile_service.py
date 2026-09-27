from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import crud_server_profile
from app.models.server_profile import ServerProfile
from app.services.errors import ServiceError


async def get_profile(db: AsyncSession) -> ServerProfile:
    profile = await crud_server_profile.get(db)
    if profile is None:
        raise ServiceError("Профиль клиента ещё не задан администратором", error_code="NO_PROFILE")
    return profile


async def update_profile(
    db: AsyncSession,
    *,
    mc_version: str,
    loader: str,
    loader_version: str | None,
    server_address: str,
    server_port: int,
) -> ServerProfile:
    return await crud_server_profile.upsert(
        db,
        mc_version=mc_version,
        loader=loader,
        loader_version=loader_version,
        server_address=server_address,
        server_port=server_port,
    )
