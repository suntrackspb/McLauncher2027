"""Закладка нашего сервера в списке «Сетевая игра» (`servers.dat`).

Без неё игрок, вылетевший с сервера или вышедший поменять настройки, видит
пустой список и вынужден перезапускать игру через лаунчер. Клиент отдельный и
только под наш сервер, поэтому файл каждый раз перезаписываем целиком одной
записью — адрес с бэка всегда актуален. Формат — несжатый NBT:
compound "" { list<compound> "servers" [ { string "name", string "ip" } ] }.
"""

import struct
from pathlib import Path

FILENAME = "servers.dat"

_STRING = 8
_LIST = 9
_COMPOUND = 10
_END = 0


def _string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack(">H", len(encoded)) + encoded


def _named(tag: int, name: str) -> bytes:
    return struct.pack(">b", tag) + _string(name)


def write_server_bookmark(minecraft_directory: Path, name: str, address: str) -> None:
    entry = (
        _named(_STRING, "name") + _string(name)
        + _named(_STRING, "ip") + _string(address)
        + struct.pack(">b", _END)
    )
    data = (
        _named(_COMPOUND, "")
        + _named(_LIST, "servers") + struct.pack(">bi", _COMPOUND, 1) + entry
        + struct.pack(">b", _END)
    )
    path = Path(minecraft_directory) / FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
