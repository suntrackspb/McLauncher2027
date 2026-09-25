import base64
import json
import re
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import crud_player
from app.models.player import Player
from app.services.errors import ServiceError

_HEX32_RE = re.compile(r"^[a-f0-9]{32}$")
_SERVER_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{39,41}$")

# TODO: скины/плащи — отдельная задача (хранение текстур + сборка URL, как в
# authlib_skinfix_by_TaoGunner-2/config.php::getSkinURL). Пока профиль отдаётся
# без textures, чтобы не блокировать auth/join/mods.


def build_profile(player: Player) -> dict:
    properties_payload = {
        "timestamp": int(time.time() * 1000),
        "profileId": player.uuid,
        "profileName": player.username,
        "textures": {},
    }
    return {
        "id": player.uuid,
        "name": player.username,
        "properties": [
            {
                "name": "textures",
                "value": base64.b64encode(json.dumps(properties_payload).encode()).decode(),
                "signature": "",
            }
        ],
    }


async def has_joined(db: AsyncSession, username: str, server_id: str) -> dict | None:
    if len(username) > 16 or not _SERVER_ID_RE.match(server_id):
        return None
    player = await crud_player.get_by_username_and_server(db, username, server_id)
    if not player:
        return None
    return build_profile(player)


async def join(db: AsyncSession, access_token: str, selected_profile: str, server_id: str) -> None:
    if not _HEX32_RE.match(access_token) or not _HEX32_RE.match(selected_profile):
        raise ServiceError("Bad arguments", error_code="IllegalArgumentException")
    if not _SERVER_ID_RE.match(server_id):
        raise ServiceError("Bad arguments", error_code="IllegalArgumentException")

    player = await crud_player.get_by_uuid_and_token(db, selected_profile, access_token)
    if not player:
        raise ServiceError("Invalid username or password", error_code="ForbiddenOperationException")

    await crud_player.set_server_id(db, player, server_id)


async def get_profile(db: AsyncSession, uuid: str) -> dict | None:
    if not _HEX32_RE.match(uuid):
        return None
    player = await crud_player.get_by_uuid(db, uuid)
    if not player:
        return None
    return build_profile(player)
