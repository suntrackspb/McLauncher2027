import pytest

from app.core.config import settings

PNG_HEADER = b"\x89PNG\r\n\x1a\n"
FAKE_PNG = PNG_HEADER + b"fake-content"
DUMMY_PASSWORD = "not-a-real-secret-3"  # noqa: S105


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
        files={"file": ("cape.png", FAKE_PNG, "image/png")},
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
