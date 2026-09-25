import secrets
import time
from pathlib import Path

import jwt

from app.core.config import settings

_TOKEN_TTL_SECONDS = 12 * 60 * 60


def _resolve_secret(configured_value: str, filename: str, *, on_generated=None) -> str:
    """Если значение задано в .env — используем его. Иначе один раз генерируем
    случайное и сохраняем рядом с остальным рантайм-стейтом, чтобы оно не
    менялось между перезапусками (иначе выданные ранее JWT/пароль отвалятся)."""
    if configured_value:
        return configured_value

    state_dir = Path(settings.admin_state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    secret_file = state_dir / filename

    if secret_file.exists():
        return secret_file.read_text().strip()

    generated = secrets.token_hex(16)
    secret_file.write_text(generated)
    if on_generated:
        on_generated(generated)
    return generated


def get_admin_password() -> str:
    return _resolve_secret(settings.admin_password, "admin_password.txt")


def get_jwt_secret() -> str:
    return _resolve_secret(settings.admin_jwt_secret, "admin_jwt_secret.txt")


def ensure_admin_credentials_ready() -> None:
    """Вызывается один раз при старте приложения (см. main.py) — если пароль
    администратора не задан в .env, генерирует его и печатает в консоль,
    иначе никто не узнает пароль от новой инсталляции."""

    def _print_generated(password: str) -> None:
        print(f"[admin] Сгенерирован пароль администратора: {password}")

    _resolve_secret(settings.admin_password, "admin_password.txt", on_generated=_print_generated)
    _resolve_secret(settings.admin_jwt_secret, "admin_jwt_secret.txt")


def create_admin_token() -> str:
    payload = {"role": "admin", "exp": int(time.time()) + _TOKEN_TTL_SECONDS}
    return jwt.encode(payload, get_jwt_secret(), algorithm="HS256")


def verify_admin_token(token: str) -> bool:
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        return False
    return payload.get("role") == "admin"
