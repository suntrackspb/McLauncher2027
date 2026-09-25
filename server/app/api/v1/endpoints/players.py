from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.auth import ErrorResponse
from app.schemas.player import TextureUploadOut
from app.services import player_service
from app.services.errors import ServiceError

router = APIRouter(prefix="/players", tags=["players"])


@router.post("/me/skin")
async def upload_skin(
    response: Response,
    uuid: str = Form(...),
    access_token: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        skin_hash = await player_service.upload_skin(db, uuid, access_token, await file.read())
    except ServiceError as exc:
        response.status_code = 403 if exc.error_code == "FORBIDDEN" else 400
        return ErrorResponse(error=exc.error_code, error_message=exc.message).model_dump(by_alias=True)
    return TextureUploadOut(ok=True, hash=skin_hash)


@router.post("/me/cape")
async def upload_cape(
    response: Response,
    uuid: str = Form(...),
    access_token: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        cape_hash = await player_service.upload_cape(db, uuid, access_token, await file.read())
    except ServiceError as exc:
        response.status_code = 403 if exc.error_code == "FORBIDDEN" else 400
        return ErrorResponse(error=exc.error_code, error_message=exc.message).model_dump(by_alias=True)
    return TextureUploadOut(ok=True, hash=cape_hash)
