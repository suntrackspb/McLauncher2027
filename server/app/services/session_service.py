import base64
import json
import re
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import crud_player
from app.models.player import Player
from app.services import texture_storage
from app.services.errors import ServiceError

_HEX32_RE = re.compile(r"^[a-f0-9]{32}$")
_SERVER_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{39,41}$")


def _build_textures(player: Player) -> dict:
    """Формат как в PHP-версии TaoGunner (config.php::getProfile) —
    {"SKIN": {"url": ...}, "CAPE": {"url": ...}}, ключ отсутствует, если у
    игрока нет загруженной текстуры этого типа."""
    textures = {}
    if player.skin_hash:
        textures["SKIN"] = {"url": texture_storage.texture_url("skin", player.skin_hash)}
    if player.cape_hash:
        textures["CAPE"] = {"url": texture_storage.texture_url("cape", player.cape_hash)}
    return textures


def build_profile(player: Player) -> dict:
    properties_payload = {
        "timestamp": int(time.time() * 1000),
        "profileId": player.uuid,
        "profileName": player.username,
        "textures": _build_textures(player),
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
