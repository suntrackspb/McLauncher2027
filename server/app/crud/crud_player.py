from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.player import Player


async def get_by_username(db: AsyncSession, username: str) -> Player | None:
    result = await db.execute(select(Player).where(Player.username == username.lower()))
    return result.scalar_one_or_none()


async def get_by_uuid(db: AsyncSession, uuid: str) -> Player | None:
    result = await db.execute(select(Player).where(Player.uuid == uuid))
    return result.scalar_one_or_none()


async def get_by_uuid_and_token(db: AsyncSession, uuid: str, access_token: str) -> Player | None:
    result = await db.execute(
        select(Player).where(Player.uuid == uuid, Player.access_token == access_token)
    )
    return result.scalar_one_or_none()


async def get_by_username_and_server(db: AsyncSession, username: str, server_id: str) -> Player | None:
    result = await db.execute(
        select(Player).where(Player.username == username.lower(), Player.server_id == server_id)
    )
    return result.scalar_one_or_none()


async def create(db: AsyncSession, *, username: str, uuid: str, password_hash: str) -> Player:
    player = Player(username=username.lower(), uuid=uuid, password_hash=password_hash)
    db.add(player)
    await db.commit()
    await db.refresh(player)
    return player


async def set_access_token(db: AsyncSession, player: Player, access_token: str) -> Player:
    player.access_token = access_token
    await db.commit()
    await db.refresh(player)
    return player


async def set_server_id(db: AsyncSession, player: Player, server_id: str) -> Player:
    player.server_id = server_id
    await db.commit()
    await db.refresh(player)
    return player


async def set_skin_hash(db: AsyncSession, player: Player, skin_hash: str) -> Player:
    player.skin_hash = skin_hash
    await db.commit()
    await db.refresh(player)
    return player


async def set_cape_hash(db: AsyncSession, player: Player, cape_hash: str) -> Player:
    player.cape_hash = cape_hash
    await db.commit()
    await db.refresh(player)
    return player
