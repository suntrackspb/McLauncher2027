import pytest

from app.core.config import settings

TEST_PASSWORD = "not-a-real-admin-secret"  # noqa: S105
FAKE_JAR = b"PK\x03\x04fake-jar-content"


@pytest.fixture(autouse=True)
def _isolated_admin_and_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "admin_password", TEST_PASSWORD)
    monkeypatch.setattr(settings, "admin_jwt_secret", "test-jwt-secret")
    monkeypatch.setattr(settings, "mods_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "public_base_url", "http://test.local")


async def _admin_token(client) -> str:
    resp = await client.post("/api/v1/admin/login", json={"password": TEST_PASSWORD})
    return resp.json()["access_token"]


async def test_login_success(client):
    resp = await client.post("/api/v1/admin/login", json={"password": TEST_PASSWORD})
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"
    assert resp.json()["access_token"]


async def test_login_wrong_password(client):
    resp = await client.post("/api/v1/admin/login", json={"password": "wrong"})
    assert resp.status_code == 403


async def test_mods_list_requires_auth(client):
    resp = await client.get("/api/v1/admin/mods")
    assert resp.status_code == 401


async def test_mods_list_rejects_bad_token(client):
    resp = await client.get("/api/v1/admin/mods", headers={"Authorization": "Bearer nonsense"})
    assert resp.status_code == 401


async def test_upload_mod_and_list(client):
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/admin/mods",
        headers=headers,
        data={"name": "JEI", "description": "Item viewer", "mod_type": "required", "loader": "forge", "mc_version": "1.20.1"},
        files={"file": ("jei.jar", FAKE_JAR, "application/java-archive")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "JEI"
    assert body["file_hash"]
    assert body["url"] == f"http://test.local/mod-files/{body['file_hash']}.jar"

    list_resp = await client.get("/api/v1/admin/mods", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    manifest_resp = await client.get(
        "/api/v1/mods/manifest", params={"loader": "forge", "mc_version": "1.20.1"}
    )
    assert len(manifest_resp.json()) == 1
    assert manifest_resp.json()[0]["name"] == "JEI"


async def test_upload_mod_rejects_non_jar(client):
    token = await _admin_token(client)
    resp = await client.post(
        "/api/v1/admin/mods",
        headers={"Authorization": f"Bearer {token}"},
        data={"name": "Bad", "mod_type": "required", "loader": "forge", "mc_version": "1.20.1"},
        files={"file": ("bad.jar", b"not a jar", "application/java-archive")},
    )
    assert resp.status_code == 400


async def test_delete_mod(client):
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    upload_resp = await client.post(
        "/api/v1/admin/mods",
        headers=headers,
        data={"name": "ToDelete", "mod_type": "optional", "loader": "forge", "mc_version": "1.20.1"},
        files={"file": ("del.jar", FAKE_JAR, "application/java-archive")},
    )
    mod_id = upload_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/admin/mods/{mod_id}", headers=headers)
    assert delete_resp.status_code == 204

    list_resp = await client.get("/api/v1/admin/mods", headers=headers)
    assert list_resp.json() == []


async def test_delete_missing_mod_returns_404(client):
    token = await _admin_token(client)
    resp = await client.delete("/api/v1/admin/mods/9999", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


async def _upload(client, headers, name, content=FAKE_JAR, mc_version="1.20.1"):
    resp = await client.post(
        "/api/v1/admin/mods",
        headers=headers,
        data={"name": name, "mod_type": "optional", "loader": "forge", "mc_version": mc_version},
        files={"file": (f"{name}.jar", content, "application/java-archive")},
    )
    return resp.json()


async def test_delete_mod_removes_file_from_disk(client, tmp_path):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    mod = await _upload(client, headers, "Gone")
    assert (tmp_path / f"{mod['file_hash']}.jar").exists()

    await client.delete(f"/api/v1/admin/mods/{mod['id']}", headers=headers)
    assert not (tmp_path / f"{mod['file_hash']}.jar").exists()


async def test_delete_keeps_file_while_another_mod_uses_it(client, tmp_path):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    first = await _upload(client, headers, "A", mc_version="1.20.1")
    second = await _upload(client, headers, "B", mc_version="1.21")
    assert first["file_hash"] == second["file_hash"]
    path = tmp_path / f"{first['file_hash']}.jar"

    await client.delete(f"/api/v1/admin/mods/{first['id']}", headers=headers)
    assert path.exists()
    await client.delete(f"/api/v1/admin/mods/{second['id']}", headers=headers)
    assert not path.exists()


async def test_update_mod_changes_only_given_fields(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    mod = await _upload(client, headers, "Old")

    resp = await client.patch(
        f"/api/v1/admin/mods/{mod['id']}",
        headers=headers,
        json={"name": "  New  ", "mod_type": "required", "description": "desc"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "New"
    assert body["mod_type"] == "required"
    assert body["description"] == "desc"
    assert body["loader"] == "forge"
    assert body["file_hash"] == mod["file_hash"]

    cleared = await client.patch(f"/api/v1/admin/mods/{mod['id']}", headers=headers, json={"description": ""})
    assert cleared.json()["description"] is None


async def test_update_mod_validation_and_auth(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    mod = await _upload(client, headers, "X")
    url = f"/api/v1/admin/mods/{mod['id']}"

    assert (await client.patch(url, json={"name": "n"})).status_code == 401
    assert (await client.patch(url, headers=headers, json={"name": "   "})).status_code == 400
    assert (await client.patch(url, headers=headers, json={"loader": None})).status_code == 422
    assert (await client.patch(url, headers=headers, json={"mod_type": "bogus"})).status_code == 422
    assert (await client.patch("/api/v1/admin/mods/9999", headers=headers, json={"name": "n"})).status_code == 404
