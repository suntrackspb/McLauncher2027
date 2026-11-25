from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator


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
    client_zip_url: str | None = Field(default=None, max_length=2083)

    @field_validator("client_zip_url")
    @classmethod
    def validate_client_zip_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            url = urlsplit(value)
            valid = (
                url.scheme in {"http", "https"} and url.hostname and url.port != 0
                and url.username is None and not any(char.isspace() for char in value)
                and not url.fragment
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("Укажите прямую HTTP(S)-ссылку на ZIP без логина и пароля")
        return value
