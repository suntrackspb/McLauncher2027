from fastapi import APIRouter

from app.api.v1.endpoints import auth, mods, session

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(session.router)
api_router.include_router(mods.router)
