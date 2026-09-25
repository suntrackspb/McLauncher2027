import re
import secrets
import uuid

import bcrypt

USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,15}$")

# Yggdrasil UUID/accessToken формат: 32-символьная hex-строка без дефисов.
OFFLINE_UUID_NAMESPACE = uuid.NAMESPACE_DNS


def is_valid_username(username: str) -> bool:
    return bool(USERNAME_RE.match(username))


def offline_uuid(username: str) -> str:
    """UUID в оффлайн-режиме Minecraft: uuid5(NAMESPACE_DNS, 'OfflinePlayer:<ник>')."""
    return uuid.uuid5(OFFLINE_UUID_NAMESPACE, f"OfflinePlayer:{username}").hex


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def generate_access_token() -> str:
    return secrets.token_hex(16)
