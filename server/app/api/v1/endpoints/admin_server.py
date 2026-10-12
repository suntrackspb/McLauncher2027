from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.admin import require_admin
from app.core.database import get_db
from app.services import server_connection_service as service
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
        "has_password": bool(conn.password_enc),
        "has_private_key": bool(conn.private_key_enc),
        "host_key": conn.host_key,
    }


def _http(exc: ServiceError) -> HTTPException:
    status = {"NO_CONNECTION": 409, "NO_PROFILE": 409, "REMOTE": 502, "NotFound": 404}.get(exc.error_code, 400)
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
