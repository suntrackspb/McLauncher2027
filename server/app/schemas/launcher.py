from pydantic import BaseModel


class LauncherVersionOut(BaseModel):
    version: str
    download_url_windows: str
    download_url_macos: str
