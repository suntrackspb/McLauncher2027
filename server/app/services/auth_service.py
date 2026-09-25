from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import crud_player
from app.core.security import (
    generate_access_token,
    hash_password,
    is_valid_username,
    offline_uuid,
    verify_password,
)
from app.models.player import Player
from app.services.errors import ServiceError


async def register(db: AsyncSession, username: str, password: str) -> Player:
    if not is_valid_username(username):
        raise ServiceError("Некорректное имя пользователя")
    if len(password) < 4:
        raise ServiceError("Пароль слишком короткий")

    if await crud_player.get_by_username(db, username):
        raise ServiceError("Пользователь с таким именем уже зарегистрирован")

    uuid = offline_uuid(username)
    if await crud_player.get_by_uuid(db, uuid):
        raise ServiceError("Пользователь с таким именем уже зарегистрирован")

    return await crud_player.create(
        db, username=username, uuid=uuid, password_hash=hash_password(password)
    )


async def login(db: AsyncSession, username: str, password: str) -> Player:
    player = await crud_player.get_by_username(db, username)
    if not player or not verify_password(password, player.password_hash):
        raise ServiceError("Неверный логин или пароль", error_code="FORBIDDEN")

    return await crud_player.set_access_token(db, player, generate_access_token())
