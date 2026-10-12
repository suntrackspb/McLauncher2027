import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secret_box
from app.crud import crud_mod
from app.models.server_connection import ServerConnection
from app.services import profile_service, server_sync
from app.services.errors import ServiceError
from app.services.remote_fs import ConnectionParams, RemoteError, open_remote

DEFAULT_PORTS = {"ftp": 21, "ftps": 21, "sftp": 22}


async def get(db: AsyncSession) -> ServerConnection | None:
    return (await db.execute(select(ServerConnection).where(ServerConnection.id == 1))).scalar_one_or_none()


async def save(
    db: AsyncSession,
    *,
    protocol: str,
    host: str,
    port: int | None,
    username: str,
    password: str | None,
    private_key: str | None,
    server_dir: str,
    reset_host_key: bool = False,
) -> ServerConnection:
    """password/private_key: None — оставить сохранённый, "" — стереть."""
    port = port or DEFAULT_PORTS[protocol]
    conn = await get(db)
    if conn is None:
        conn = ServerConnection(id=1)
        db.add(conn)
    if conn.host != host or conn.port != port or reset_host_key:
        conn.host_key = None
    conn.protocol = protocol
    conn.host = host
    conn.port = port
    conn.username = username
    conn.server_dir = server_dir.rstrip("/") or "/"
    if password is not None:
        conn.password_enc = secret_box.encrypt(password)
    if private_key is not None:
        conn.private_key_enc = secret_box.encrypt(private_key)
    if protocol != "sftp":
        conn.private_key_enc = None
    await db.commit()
    await db.refresh(conn)
    return conn


def _params(conn: ServerConnection) -> ConnectionParams:
    return ConnectionParams(
        protocol=conn.protocol,
        host=conn.host,
        port=conn.port,
        username=conn.username,
        password=secret_box.decrypt(conn.password_enc),
        private_key=secret_box.decrypt(conn.private_key_enc),
        host_key=conn.host_key,
        server_dir=conn.server_dir,
    )


async def _require(db: AsyncSession) -> ServerConnection:
    conn = await get(db)
    if conn is None:
        raise ServiceError("Подключение к серверу не настроено", error_code="NO_CONNECTION")
    return conn


async def _remember_host_key(db: AsyncSession, conn: ServerConnection, host_key: str | None) -> None:
    if host_key and conn.host_key != host_key:
        conn.host_key = host_key
        await db.commit()


async def test(db: AsyncSession) -> dict:
    conn = await _require(db)

    def run():
        with open_remote(_params(conn)) as fs:
            names = {e.name for e in fs.list_dir("")}
            return fs.host_key, {
                "mods_dir": "mods" in names,
                "libraries_dir": "libraries" in names,
                "server_properties": "server.properties" in names,
            }

    try:
        host_key, found = await asyncio.to_thread(run)
    except RemoteError as exc:
        raise ServiceError(str(exc), error_code="REMOTE") from exc
    await _remember_host_key(db, conn, host_key)
    return {"ok": True, **found}


async def sync(db: AsyncSession, *, apply: bool) -> dict:
    conn = await _require(db)
    profile = await profile_service.get_profile(db)
    loader = profile.loader.lower()
    mods = [
        server_sync.ModToSync(m.file_name, m.file_hash, m.size)
        for m in await crud_mod.get_all(db)
        if m.server_side and m.loader.lower() == loader and m.mc_version == profile.mc_version
    ]

    def run():
        with open_remote(_params(conn)) as fs:
            # Vanilla без модов — папку mods не трогаем вовсе.
            return fs.host_key, server_sync.sync(fs, mods, apply=apply, sync_mods=loader != "vanilla")

    try:
        host_key, report = await asyncio.to_thread(run)
    except RemoteError as exc:
        raise ServiceError(str(exc), error_code="REMOTE") from exc
    await _remember_host_key(db, conn, host_key)
    return report.to_dict()
