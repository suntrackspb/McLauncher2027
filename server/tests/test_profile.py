import pytest

from app.core.config import settings

TEST_PASSWORD = "not-a-real-admin-secret"  # noqa: S105


@pytest.fixture(autouse=True)
def _isolated_admin(monkeypatch):
    monkeypatch.setattr(settings, "admin_password", TEST_PASSWORD)
    monkeypatch.setattr(settings, "admin_jwt_secret", "test-jwt-secret")


async def _admin_headers(client) -> dict:
    resp = await client.post("/api/v1/admin/login", json={"password": TEST_PASSWORD})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


_PROFILE_PAYLOAD = {
    "mc_version": "1.20.1",
    "loader": "forge",
    "loader_version": "47.4.13",
    "server_address": "127.0.0.1",
    "server_port": 25565,
}


async def test_public_profile_404_when_not_set(client):
    resp = await client.get("/api/v1/launcher/profile")
    assert resp.status_code == 404


async def test_admin_can_set_and_public_can_read_profile(client):
    headers = await _admin_headers(client)

    put_resp = await client.put("/api/v1/admin/profile", headers=headers, json=_PROFILE_PAYLOAD)
    assert put_resp.status_code == 200
    assert put_resp.json() == _PROFILE_PAYLOAD

    get_resp = await client.get("/api/v1/launcher/profile")
    assert get_resp.status_code == 200
    assert get_resp.json() == _PROFILE_PAYLOAD


async def test_admin_profile_requires_auth(client):
    resp = await client.put("/api/v1/admin/profile", json=_PROFILE_PAYLOAD)
    assert resp.status_code == 401


async def test_updating_profile_replaces_previous_value(client):
    headers = await _admin_headers(client)
    await client.put("/api/v1/admin/profile", headers=headers, json=_PROFILE_PAYLOAD)

    vanilla_payload = {
        "mc_version": "26.1.2",
        "loader": "vanilla",
        "loader_version": None,
        "server_address": "127.0.0.1",
        "server_port": 25565,
    }
    put_resp = await client.put("/api/v1/admin/profile", headers=headers, json=vanilla_payload)
    assert put_resp.status_code == 200
    assert put_resp.json() == vanilla_payload

    get_resp = await client.get("/api/v1/launcher/profile")
    assert get_resp.json() == vanilla_payload
