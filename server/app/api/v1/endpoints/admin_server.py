from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.admin import require_admin
from app.core.database import get_db
from app.services import server_connection_service as service
from app.services import server_control_service as control
from app.services.errors import ServiceError

router = APIRouter(prefix="/admin/server", tags=["admin"], dependencies=[Depends(require_admin)])


class ConnectionIn(BaseModel):
    protocol: Literal["ftp", "ftps", "sftp"]
    host: str = Field(min_length=1, max_length=255)
    port: int | None = Field(None, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=128)
    # None — не менять сохранённое, "" — стереть
    password: str | None = None
    private_key: str | None = None
    server_dir: str = Field(min_length=1, max_length=512)
    service_name: str | None = Field(None, pattern=r"^[A-Za-z0-9@._-]{0,128}$")
    reset_host_key: bool = False


def _out(conn) -> dict | None:
    if conn is None:
        return None
    # Секреты наружу не отдаём — только факт, что они заданы.
    return {
        "protocol": conn.protocol,
        "host": conn.host,
        "port": conn.port,
        "username": conn.username,
        "server_dir": conn.server_dir,
        "service_name": conn.service_name,
        "has_password": bool(conn.password_enc),
        "has_private_key": bool(conn.private_key_enc),
        "host_key": conn.host_key,
    }


def _http(exc: ServiceError) -> HTTPException:
    status = {"NO_CONNECTION": 409, "NO_PROFILE": 409, "UNSUPPORTED": 409, "REMOTE": 502, "NotFound": 404}.get(exc.error_code, 400)
    return HTTPException(status_code=status, detail=exc.message)


@router.get("/connection")
async def get_connection(db: AsyncSession = Depends(get_db)):
    return _out(await service.get(db))


@router.put("/connection")
async def put_connection(payload: ConnectionIn, db: AsyncSession = Depends(get_db)):
    return _out(await service.save(db, **payload.model_dump()))


@router.post("/connection/test")
async def test_connection(db: AsyncSession = Depends(get_db)):
    try:
        return await service.test(db)
    except ServiceError as exc:
        raise _http(exc) from exc


@router.get("/sync")
async def sync_plan(db: AsyncSession = Depends(get_db)):
    try:
        return await service.sync(db, apply=False)
    except ServiceError as exc:
        raise _http(exc) from exc


@router.post("/sync")
async def sync_apply(db: AsyncSession = Depends(get_db)):
    try:
        return await service.sync(db, apply=True)
    except ServiceError as exc:
        raise _http(exc) from exc


class RconIn(BaseModel):
    command: str = Field(min_length=1, max_length=1000)


@router.get("/status")
async def server_status(db: AsyncSession = Depends(get_db)):
    try:
        return await control.status(db)
    except ServiceError as exc:
        raise _http(exc) from exc


@router.post("/control/{action}")
async def server_control(action: Literal["start", "stop", "restart"], db: AsyncSession = Depends(get_db)):
    try:
        return await control.control(db, action)
    except ServiceError as exc:
        raise _http(exc) from exc


@router.get("/log")
async def server_log(lines: int = Query(200, ge=1, le=2000), db: AsyncSession = Depends(get_db)):
    try:
        return await control.log_tail(db, lines)
    except ServiceError as exc:
        raise _http(exc) from exc


@router.post("/rcon")
async def server_rcon(payload: RconIn, db: AsyncSession = Depends(get_db)):
    try:
        return await control.run_rcon(db, payload.command)
    except ServiceError as exc:
        raise _http(exc) from exc


@router.post("/rcon/enable")
async def server_enable_rcon(db: AsyncSession = Depends(get_db)):
    try:
        return await control.enable_rcon(db)
    except ServiceError as exc:
        raise _http(exc) from exc
