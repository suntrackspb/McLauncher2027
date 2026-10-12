"""Минимальный клиент Source RCON (его же использует Minecraft):
https://minecraft.wiki/w/RCON. Синхронный — вызывать через asyncio.to_thread."""

import socket
import struct

TIMEOUT = 10
_AUTH, _COMMAND = 3, 2


class RconError(Exception):
    pass


def _send(sock: socket.socket, req_id: int, kind: int, body: str) -> None:
    payload = struct.pack("<ii", req_id, kind) + body.encode("utf-8") + b"\x00\x00"
    sock.sendall(struct.pack("<i", len(payload)) + payload)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise RconError("RCON: сервер закрыл соединение")
        data += chunk
    return data


def _recv(sock: socket.socket) -> tuple[int, str]:
    (length,) = struct.unpack("<i", _recv_exact(sock, 4))
    packet = _recv_exact(sock, length)
    req_id, _kind = struct.unpack("<ii", packet[:8])
    return req_id, packet[8:-2].decode("utf-8", errors="replace")


def command(host: str, port: int, password: str, cmd: str) -> str:
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT) as sock:
            _send(sock, 1, _AUTH, password)
            req_id, _ = _recv(sock)
            if req_id == -1:
                raise RconError("RCON: неверный пароль")
            _send(sock, 2, _COMMAND, cmd)
            _, body = _recv(sock)
            return body
    except OSError as exc:
        raise RconError(f"RCON: нет подключения к {host}:{port} ({exc})") from exc
