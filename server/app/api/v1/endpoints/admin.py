import hmac

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import admin_auth
from app.core.database import get_db
from app.models.mod import ModType
from app.schemas.admin import AdminLoginRequest, AdminLoginResponse
from app.schemas.mod import ModOut
from app.services import mod_service
from app.services.errors import ServiceError

router = APIRouter(prefix="/admin", tags=["admin"])

_bearer = HTTPBearer(auto_error=False)


def require_admin(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
    if not credentials or not admin_auth.verify_admin_token(credentials.credentials):
        raise HTTPException(status_code=401, detail="Требуется авторизация администратора")


@router.post("/login", response_model=AdminLoginResponse)
async def login(payload: AdminLoginRequest):
    if not hmac.compare_digest(payload.password, admin_auth.get_admin_password()):
        raise HTTPException(status_code=403, detail="Неверный пароль")
    return AdminLoginResponse(access_token=admin_auth.create_admin_token())


@router.get("/mods", response_model=list[ModOut], dependencies=[Depends(require_admin)])
async def list_mods(db: AsyncSession = Depends(get_db)):
    return await mod_service.list_all_mods(db)


@router.post("/mods", response_model=ModOut, dependencies=[Depends(require_admin)])
async def upload_mod(
    name: str = Form(...),
    description: str | None = Form(None),
    mod_type: ModType = Form(...),
    loader: str = Form(...),
    mc_version: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        mod = await mod_service.upload_mod(
            db,
            name=name,
            description=description,
            file_name=file.filename or "mod.jar",
            mod_type=mod_type,
            loader=loader,
            mc_version=mc_version,
            content=await file.read(),
        )
    except ServiceError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return mod


@router.delete("/mods/{mod_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_mod(mod_id: int, db: AsyncSession = Depends(get_db)):
    try:
        await mod_service.delete_mod(db, mod_id)
    except ServiceError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
