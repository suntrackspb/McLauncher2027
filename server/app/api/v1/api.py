from fastapi import APIRouter

from app.api.v1.endpoints import auth, launcher, mods, session

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(session.router)
api_router.include_router(mods.router)
api_router.include_router(launcher.router)
