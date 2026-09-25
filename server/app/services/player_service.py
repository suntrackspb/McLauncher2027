from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import crud_player
from app.services import texture_storage
from app.services.errors import ServiceError


async def _authorize(db: AsyncSession, uuid: str, access_token: str):
    player = await crud_player.get_by_uuid_and_token(db, uuid, access_token)
    if not player:
        raise ServiceError("Неверный uuid или access_token", error_code="FORBIDDEN")
    return player


async def upload_skin(db: AsyncSession, uuid: str, access_token: str, content: bytes) -> str:
    player = await _authorize(db, uuid, access_token)
    skin_hash = texture_storage.save_texture("skin", content)
    await crud_player.set_skin_hash(db, player, skin_hash)
    return skin_hash


async def upload_cape(db: AsyncSession, uuid: str, access_token: str, content: bytes) -> str:
    player = await _authorize(db, uuid, access_token)
    cape_hash = texture_storage.save_texture("cape", content)
    await crud_player.set_cape_hash(db, player, cape_hash)
    return cape_hash
