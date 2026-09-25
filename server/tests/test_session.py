SERVER_ID = "a" * 40
# Не настоящие учётные данные — фикстура для тестов сессии.
DUMMY_PASSWORD = "not-a-real-secret-2"  # noqa: S105


async def _register_and_login(client, username="Steve", password=DUMMY_PASSWORD):
    await client.post("/api/v1/auth/register", json={"username": username, "password": password})
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.json()


async def test_join_and_has_joined(client):
    login = await _register_and_login(client)

    join_resp = await client.post(
        "/api/v1/join",
        json={
            "accessToken": login["accessToken"],
            "selectedProfile": login["UUID"],
            "serverId": SERVER_ID,
        },
    )
    assert join_resp.status_code == 204

    has_joined_resp = await client.get(
        "/api/v1/hasJoined", params={"username": login["username"], "serverId": SERVER_ID}
    )
    assert has_joined_resp.status_code == 200
    assert has_joined_resp.json()["id"] == login["UUID"]


async def test_join_with_wrong_token_is_forbidden(client):
    login = await _register_and_login(client)

    resp = await client.post(
        "/api/v1/join",
        json={"accessToken": "0" * 32, "selectedProfile": login["UUID"], "serverId": SERVER_ID},
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "ForbiddenOperationException"


async def test_has_joined_without_join_returns_no_content(client):
    login = await _register_and_login(client)
    resp = await client.get(
        "/api/v1/hasJoined", params={"username": login["username"], "serverId": SERVER_ID}
    )
    assert resp.status_code == 204


async def test_profile_by_uuid(client):
    login = await _register_and_login(client)
    resp = await client.get("/api/v1/profile", params={"uuid": login["UUID"]})
    assert resp.status_code == 200
    assert resp.json()["name"] == login["username"]


async def test_profile_includes_textures_after_skin_upload(client, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "textures_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "public_base_url", "http://test.local")

    login = await _register_and_login(client)
    fake_png = b"\x89PNG\r\n\x1a\n" + b"fake-content"
    upload_resp = await client.post(
        "/api/v1/players/me/skin",
        data={"uuid": login["UUID"], "access_token": login["accessToken"]},
        files={"file": ("skin.png", fake_png, "image/png")},
    )
    skin_hash = upload_resp.json()["hash"]

    resp = await client.get("/api/v1/profile", params={"uuid": login["UUID"]})
    assert resp.status_code == 200

    import base64
    import json

    properties = resp.json()["properties"][0]
    payload = json.loads(base64.b64decode(properties["value"]))
    assert payload["textures"]["SKIN"]["url"] == f"http://test.local/textures/skin/{skin_hash}.png"
    assert "CAPE" not in payload["textures"]
