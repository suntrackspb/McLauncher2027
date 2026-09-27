from pydantic import BaseModel


class LauncherVersionOut(BaseModel):
    version: str
    download_url_windows: str
    download_url_macos: str
    updater_url_windows: str
    updater_url_macos: str


class ServerProfileOut(BaseModel):
    mc_version: str
    loader: str
    loader_version: str | None
    server_address: str
    server_port: int

    model_config = {"from_attributes": True}
