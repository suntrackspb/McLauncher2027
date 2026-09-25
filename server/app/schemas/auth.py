from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str = "OK"
    username: str
    uuid: str = Field(serialization_alias="UUID")
    access_token: str = Field(serialization_alias="accessToken")


class JoinRequest(BaseModel):
    accessToken: str
    selectedProfile: str
    serverId: str


class ErrorResponse(BaseModel):
    """Формат ошибок Yggdrasil-протокола (wiki.vg/Authentication#Errors) — поля
    camelCase обязательны, их ждёт клиент Minecraft/Forge/Fabric, а не наш фронт."""

    model_config = ConfigDict(populate_by_name=True)

    error: str
    error_message: str = Field(serialization_alias="errorMessage")
    cause: str = ""
