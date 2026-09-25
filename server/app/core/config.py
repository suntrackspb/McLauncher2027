from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./launcher.db"
    default_mc_version: str = "1.20.1"
    default_loader: str = "forge"


settings = Settings()
