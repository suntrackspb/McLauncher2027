"""Управление игровым сервером: статус/старт/стоп/рестарт (systemd по SSH),
лог (logs/latest.log — через SFTP или FTP) и консоль через RCON.

RCON доступен в обоих режимах: порт и пароль берутся из server.properties,
подключение идёт на адрес сервера из профиля (туда же, куда ходят игроки).
"""

import asyncio
import re
import secrets
import shlex

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import profile_service, rcon
from app.services.errors import ServiceError
from app.services.remote_fs import RemoteError, RemoteFS, SftpFS, open_remote
from app.services.server_connection_service import _params, _remember_host_key, _require

SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9@._-]{1,128}$")
ACTIONS = ("start", "stop", "restart")
LOG_PATH = "logs/latest.log"
LOG_MAX_BYTES = 256 * 1024


PROPS_PATH = "server.properties"
PROP_KEY_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_ESCAPES = {"t": "\t", "n": "\n", "r": "\r", "f": "\f"}


def _unescape(value: str) -> str:
    r"""Экранирование Java Properties: Minecraft пишет «\:», «\=», «\uXXXX»."""
    out, i = [], 0
    while i < len(value):
        ch = value[i]
        if ch != "\\" or i + 1 == len(value):
            out.append(ch)
            i += 1
            continue
        nxt = value[i + 1]
        if nxt == "u" and re.fullmatch(r"[0-9a-fA-F]{4}", value[i + 2:i + 6]):
            out.append(chr(int(value[i + 2:i + 6], 16)))
            i += 6
            continue
        out.append(_ESCAPES.get(nxt, nxt))
        i += 2
    return "".join(out)


def _escape(value: str) -> str:
    out = []
    for i, ch in enumerate(value):
        if ch in "\\=:#!":
            out.append("\\" + ch)
        elif ch == " " and i == 0:
            out.append("\\ ")
        elif ch in "\t\n\r\f":
            out.append("\\" + {"\t": "t", "\n": "n", "\r": "r", "\f": "f"}[ch])
        elif ord(ch) > 0x7E or ord(ch) < 0x20:
            # Так файл читается одинаково при любой кодировке, в которой его откроет сервер.
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return "".join(out)


def parse_properties(text: str) -> dict[str, str]:
    props = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "!")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        props[key.strip()] = _unescape(value.strip())
    return props


def set_properties(text: str, updates: dict[str, str]) -> str:
    """Меняет значения на месте, сохраняя комментарии и порядок; новых
    ключей дописывает в конец."""
    left = dict(updates)
    lines = []
    for line in text.splitlines():
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith(("#", "!")) else None
        if key in left:
            lines.append(f"{key}={_escape(left.pop(key))}")
        else:
            lines.append(line)
    lines += [f"{k}={_escape(v)}" for k, v in left.items()]
    return "\n".join(lines) + "\n"


async def _with_fs(db: AsyncSession, fn):
    conn = await _require(db)

    def run():
        with open_remote(_params(conn)) as fs:
            return fs.host_key, fn(fs, conn)

    try:
        host_key, result = await asyncio.to_thread(run)
    except RemoteError as exc:
        raise ServiceError(str(exc), error_code="REMOTE") from exc
    await _remember_host_key(db, conn, host_key)
    return result


_UNIT_DIRS = "/etc/systemd/system /lib/systemd/system /usr/lib/systemd/system"


def _service_name(fs: RemoteFS, conn) -> str | None:
    """Имя systemd-сервиса: из настроек, а если не указано — ищем unit,
    у которого WorkingDirectory совпадает с папкой сервера. Так управление
    работает на свежей VM без ручной настройки."""
    if not isinstance(fs, SftpFS):
        return None
    if conn.service_name:
        return conn.service_name
    root = conn.server_dir.rstrip("/") or "/"
    patterns = " ".join(
        f"-e {shlex.quote(f'WorkingDirectory={d}')}" for d in (root, root + "/")
    )
    _, out = fs.run(
        f"for d in {_UNIT_DIRS}; do grep -lsxF {patterns} \"$d\"/*.service; done"
    )
    for line in out.splitlines():
        name = line.strip().rsplit("/", 1)[-1]
        if name.endswith(".service"):
            return name.removesuffix(".service")
    return None


def _require_ssh(fs: RemoteFS, conn) -> str:
    if not isinstance(fs, SftpFS):
        raise ServiceError(
            "Управление запуском доступно только по SFTP/SSH. На хостинге используйте панель хостера.",
            error_code="UNSUPPORTED",
        )
    service = _service_name(fs, conn)
    if not service:
        raise ServiceError(
            f"Не найден systemd-сервис с WorkingDirectory={conn.server_dir} — укажите его в настройках подключения",
            error_code="UNSUPPORTED",
        )
    return shlex.quote(service)


def _systemctl(fs: SftpFS, conn, action: str, unit: str) -> str:
    # root — как есть; другой пользователь — через sudo (без пароля).
    prefix = "" if conn.username == "root" else "sudo -n "
    code, out = fs.run(f"{prefix}systemctl {action} {unit}", timeout=120)
    if code != 0:
        if "password is required" in out or "not allowed" in out or "may not run" in out:
            raise ServiceError(
                f"Нет прав: пользователю нужен sudo без пароля на «systemctl {action} {unit}». {out}",
                error_code="REMOTE",
            )
        raise ServiceError(f"systemctl {action} завершился с кодом {code}: {out}", error_code="REMOTE")
    _, state = fs.run(f"systemctl is-active {unit}")
    return state.splitlines()[-1] if state else "unknown"


def _read_props(fs: RemoteFS) -> dict[str, str]:
    try:
        return parse_properties(fs.read(PROPS_PATH).decode("utf-8", errors="replace"))
    except RemoteError:
        return {}


async def _rcon_target(db: AsyncSession, props: dict[str, str]) -> tuple[str, int, str] | None:
    if props.get("enable-rcon", "false").lower() != "true" or not props.get("rcon.password"):
        return None
    profile = await profile_service.get_profile(db)
    return profile.server_address, int(props.get("rcon.port") or 25575), props["rcon.password"]


async def status(db: AsyncSession) -> dict:
    def fn(fs, conn):
        props = _read_props(fs)
        state = None
        service = _service_name(fs, conn)
        if service:
            _, out = fs.run(f"systemctl is-active {shlex.quote(service)}")
            state = out.splitlines()[-1] if out else "unknown"
        return props, state, service

    props, state, service = await _with_fs(db, fn)
    target = await _rcon_target(db, props)
    players = None
    rcon_error = None
    if target:
        try:
            players = await asyncio.to_thread(rcon.command, *target, "list")
        except rcon.RconError as exc:
            rcon_error = str(exc)
    return {
        "service_state": state,  # active / inactive / failed / activating… или None без SSH
        "can_control": service is not None,
        "service_name": service,
        "rcon_enabled": target is not None,
        "rcon_error": rcon_error,
        "players": players,
    }


async def control(db: AsyncSession, action: str) -> dict:
    if action not in ACTIONS:
        raise ServiceError("Неизвестное действие", error_code="BadRequest")

    def fn(fs, conn):
        unit = _require_ssh(fs, conn)
        return {"ok": True, "service_state": _systemctl(fs, conn, action, unit)}

    return await _with_fs(db, fn)


async def log_tail(db: AsyncSession, lines: int) -> dict:
    def fn(fs, conn):
        try:
            data = fs.read_tail(LOG_PATH, LOG_MAX_BYTES)
        except RemoteError:
            return {"lines": [], "missing": True}
        text = data.decode("utf-8", errors="replace").splitlines()
        if len(data) == LOG_MAX_BYTES and text:
            text = text[1:]  # первая строка обрезана посередине
        return {"lines": text[-lines:], "missing": False}

    return await _with_fs(db, fn)


async def run_rcon(db: AsyncSession, cmd: str) -> dict:
    props = await _with_fs(db, lambda fs, conn: _read_props(fs))
    target = await _rcon_target(db, props)
    if target is None:
        raise ServiceError("RCON выключен в server.properties", error_code="UNSUPPORTED")
    try:
        return {"output": await asyncio.to_thread(rcon.command, *target, cmd)}
    except rcon.RconError as exc:
        raise ServiceError(str(exc), error_code="REMOTE") from exc


async def enable_rcon(db: AsyncSession) -> dict:
    def fn(fs, conn):
        text = fs.read(PROPS_PATH).decode("utf-8", errors="replace")
        props = parse_properties(text)
        updates = {"enable-rcon": "true"}
        if not props.get("rcon.port"):
            updates["rcon.port"] = "25575"
        if not props.get("rcon.password"):
            updates["rcon.password"] = secrets.token_urlsafe(18)
        fs.write(PROPS_PATH, set_properties(text, updates).encode("utf-8"))
        # Minecraft читает server.properties только при старте. Если сервером
        # управляем сами — перезапускаем сразу, а не отправляем админа в консоль.
        service = _service_name(fs, conn)
        if service:
            unit = shlex.quote(service)
            _, state = fs.run(f"systemctl is-active {unit}")
            if state.strip().splitlines()[-1:] == ["active"]:
                _systemctl(fs, conn, "restart", unit)
                return {"ok": True, "restarted": True, "needs_restart": False}
            return {"ok": True, "restarted": False, "needs_restart": False}
        return {"ok": True, "restarted": False, "needs_restart": True}

    return await _with_fs(db, fn)


async def read_properties(db: AsyncSession) -> dict:
    def fn(fs, conn):
        try:
            text = fs.read(PROPS_PATH).decode("utf-8", errors="replace")
        except RemoteError:
            return {"exists": False, "values": {}, "can_control": _service_name(fs, conn) is not None}
        return {"exists": True, "values": parse_properties(text), "can_control": _service_name(fs, conn) is not None}

    return await _with_fs(db, fn)


async def write_properties(db: AsyncSession, updates: dict[str, str]) -> dict:
    for key, value in updates.items():
        if not PROP_KEY_RE.match(key):
            raise ServiceError(f"Недопустимое имя параметра: {key}", error_code="BadRequest")
        if "\n" in value or "\r" in value:
            raise ServiceError(f"{key}: значение должно быть в одну строку", error_code="BadRequest")

    def fn(fs, conn):
        try:
            text = fs.read(PROPS_PATH).decode("utf-8", errors="replace")
        except RemoteError:
            text = ""
        new_text = set_properties(text, updates) if updates else text
        if new_text != text:
            fs.write(PROPS_PATH, new_text.encode("utf-8"))
        return {"exists": True, "values": parse_properties(new_text), "can_control": _service_name(fs, conn) is not None}

    return await _with_fs(db, fn)
