from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.auth import ErrorResponse, JoinRequest
from app.services import session_service
from app.services.errors import ServiceError

router = APIRouter(tags=["session"])

# Эндпоинты ниже реализуют Yggdrasil session-протокол (wiki.vg/Protocol_Encryption),
# который использует ванильный клиент/Forge/Fabric для проверки логина игрока и
# получения скина. Пути и формат ошибок совместимы с PHP-версией TaoGunner —
# это поведение проверено и его нельзя менять произвольно.


@router.get("/hasJoined")
async def has_joined(username: str, serverId: str, db: AsyncSession = Depends(get_db)):
    profile = await session_service.has_joined(db, username, serverId)
    if profile is None:
        return Response(status_code=204)
    return profile


@router.post("/join", status_code=204)
async def join(payload: JoinRequest, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        await session_service.join(db, payload.accessToken, payload.selectedProfile, payload.serverId)
    except ServiceError as exc:
        response.status_code = 403 if exc.error_code == "ForbiddenOperationException" else 400
        return ErrorResponse(error=exc.error_code, error_message=exc.message).model_dump(by_alias=True)
    return Response(status_code=204)


@router.get("/profile")
async def profile(uuid: str, db: AsyncSession = Depends(get_db)):
    result = await session_service.get_profile(db, uuid)
    if result is None:
        return Response(status_code=404)
    return result
