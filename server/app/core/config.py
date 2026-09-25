from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./launcher.db"
    default_mc_version: str = "1.20.1"
    default_loader: str = "forge"

    # Репозиторий, где собираются клиент и updater (GitHub Releases) — бэкенд сам
    # смотрит последний релиз, версию/ссылки на сборки вручную не прописываем.
    launcher_github_repo: str = ""  # "owner/name"
    # Подстроки в имени asset'а релиза, по которым отличаем сборки под ОС.
    launcher_asset_windows_hint: str = "windows"
    launcher_asset_macos_hint: str = "macos"

    # Публичный адрес бэкенда — нужен, чтобы собрать абсолютный URL текстуры
    # для Yggdrasil-профиля (клиент/Forge не умеют в относительные ссылки).
    # По аналогии со статическим $URL_SKINS в PHP-версии TaoGunner.
    public_base_url: str = ""
    textures_storage_dir: str = "./storage/textures"


settings = Settings()
