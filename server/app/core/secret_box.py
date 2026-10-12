"""Шифрование секретов подключения к игровому серверу (пароль FTP/SSH,
приватный ключ) перед записью в БД. Утечка дампа БД без файла ключа не
раскрывает доступ к серверу."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.admin_auth import _resolve_secret
from app.core.config import settings


def _fernet() -> Fernet:
    secret = _resolve_secret(settings.connection_secret, "connection_secret.txt")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def encrypt(value: str | None) -> str | None:
    if not value:
        return None
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Не удалось расшифровать секрет — сменился connection_secret?") from exc
