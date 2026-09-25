from fastapi import FastAPI

from app.api.v1.api import api_router

app = FastAPI(title="McLauncher2027 backend")
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
