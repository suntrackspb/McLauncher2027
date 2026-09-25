from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest
from app.services import auth_service
from app.services.errors import ServiceError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        player = await auth_service.register(db, payload.username, payload.password)
    except ServiceError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

    return {"status": "OK", "username": player.username, "uuid": player.uuid}


@router.post("/login", response_model=LoginResponse, response_model_by_alias=True)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        player = await auth_service.login(db, payload.username, payload.password)
    except ServiceError as exc:
        status_code = 403 if exc.error_code == "FORBIDDEN" else 400
        raise HTTPException(status_code=status_code, detail=exc.message) from exc

    return LoginResponse(username=player.username, uuid=player.uuid, access_token=player.access_token)
