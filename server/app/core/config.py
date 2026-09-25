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
    mods_storage_dir: str = "./storage/mods"

    # Пароль администратора для /api/v1/admin/login. Если не задан явно —
    # генерируется случайно при первом запуске и сохраняется в
    # `<state_dir>/admin_password.txt` (см. app/core/admin_auth.py), чтобы не
    # меняться между перезапусками и не требовать отдельной админ-регистрации.
    admin_password: str = ""
    # Секрет для подписи JWT админ-токенов — та же логика: задан в .env или
    # сгенерирован один раз и сохранён в `<state_dir>/admin_jwt_secret.txt`.
    admin_jwt_secret: str = ""
    admin_state_dir: str = "./storage"


settings = Settings()
