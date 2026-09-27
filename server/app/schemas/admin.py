from pydantic import BaseModel


class AdminLoginRequest(BaseModel):
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ServerProfileUpdate(BaseModel):
    mc_version: str
    loader: str
    loader_version: str | None = None
    server_address: str
    server_port: int
