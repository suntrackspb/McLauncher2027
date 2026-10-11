import secrets
import struct
import pytest

from app.core.config import settings

PNG_HEADER = b"\x89PNG\r\n\x1a\n"


def _png(width: int, height: int) -> bytes:
    """Минимальный PNG: сигнатура + IHDR — сервер смотрит только на них."""
    ihdr = struct.pack(">II", width, height) + b"\x08\x06\x00\x00\x00"
    return PNG_HEADER + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00\x00\x00\x00" + b"fake-content"


FAKE_PNG = _png(64, 64)
FAKE_CAPE = _png(64, 32)
# Случайный на каждый прогон — без строковых литералов, на которые
# срабатывают сканеры секретов (GitGuardian).
DUMMY_PASSWORD = secrets.token_urlsafe(12)


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "textures_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "public_base_url", "http://test.local")


async def _register_and_login(client, username="Alex", password=DUMMY_PASSWORD):
    await client.post("/api/v1/auth/register", json={"username": username, "password": password})
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.json()


async def test_upload_skin_success(client):
    login = await _register_and_login(client)

    resp = await client.post(
        "/api/v1/players/me/skin",
        data={"uuid": login["UUID"], "access_token": login["accessToken"]},
        files={"file": ("skin.png", FAKE_PNG, "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert len(body["hash"]) == 32


async def test_upload_cape_success(client):
    login = await _register_and_login(client)

    resp = await client.post(
        "/api/v1/players/me/cape",
        data={"uuid": login["UUID"], "access_token": login["accessToken"]},
        files={"file": ("cape.png", FAKE_CAPE, "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert len(body["hash"]) == 32


async def test_upload_skin_with_wrong_token_is_forbidden(client):
    login = await _register_and_login(client)

    resp = await client.post(
        "/api/v1/players/me/skin",
        data={"uuid": login["UUID"], "access_token": "0" * 32},
        files={"file": ("skin.png", FAKE_PNG, "image/png")},
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "FORBIDDEN"


async def test_upload_skin_rejects_non_png(client):
    login = await _register_and_login(client)

    resp = await client.post(
        "/api/v1/players/me/skin",
        data={"uuid": login["UUID"], "access_token": login["accessToken"]},
        files={"file": ("skin.png", b"not a png", "image/png")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "BadRequest"


async def _textures(client, uuid):
    import base64
    import json

    resp = await client.get("/api/v1/profile", params={"uuid": uuid})
    value = resp.json()["properties"][0]["value"]
    return json.loads(base64.b64decode(value))["textures"]


@pytest.mark.parametrize("kind,content", [("skin", FAKE_PNG), ("cape", FAKE_CAPE)])
async def test_delete_texture_removes_it_from_profile(client, kind, content):
    login = await _register_and_login(client)
    auth = {"uuid": login["UUID"], "access_token": login["accessToken"]}
    await client.post(f"/api/v1/players/me/{kind}", data=auth, files={"file": ("t.png", content, "image/png")})
    assert kind.upper() in await _textures(client, login["UUID"])

    resp = await client.request("DELETE", f"/api/v1/players/me/{kind}", data=auth)

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert kind.upper() not in await _textures(client, login["UUID"])


async def test_delete_skin_with_wrong_token_is_forbidden(client):
    login = await _register_and_login(client)

    resp = await client.request(
        "DELETE", "/api/v1/players/me/skin", data={"uuid": login["UUID"], "access_token": "0" * 32}
    )
    assert resp.status_code == 403
