from pydantic import BaseModel, HttpUrl, field_validator


class LauncherVersionOut(BaseModel):
    version: str
    download_url_windows: str
    download_url_macos: str
    updater_url_windows: str = ""
    updater_url_macos: str = ""


class UpdaterUrls(BaseModel):
    updater_url_windows: HttpUrl | None
    updater_url_macos: HttpUrl | None

    model_config = {"from_attributes": True}

    @field_validator("updater_url_windows", "updater_url_macos")
    @classmethod
    def validate_updater_url(cls, url: HttpUrl | None) -> HttpUrl | None:
        if url is not None and (
            url.scheme != "https" or url.username is not None
            or url.password is not None or url.fragment is not None
        ):
            raise ValueError("Укажите прямую HTTPS-ссылку без логина, пароля и фрагмента")
        return url


class AuthlibJarOut(BaseModel):
    version: str
    url: str
    # Чтобы клиент заметил перепатченный jar (например, сменился адрес
    # бэкенда), а не держал старую копию из кэша вечно.
    sha256: str


class ServerProfileOut(BaseModel):
    mc_version: str
    loader: str
    loader_version: str | None
    server_address: str
    server_port: int
    client_zip_url: str | None = None

    model_config = {"from_attributes": True}
