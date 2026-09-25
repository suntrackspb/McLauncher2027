from pydantic import BaseModel


class LauncherVersionOut(BaseModel):
    version: str
    download_url_windows: str
    download_url_macos: str
    updater_url_windows: str
    updater_url_macos: str
