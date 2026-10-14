import hashlib
import json

import httpx
import pytest

from app.core.config import settings
from app.services import modrinth_service
from tests.test_admin import TEST_PASSWORD

JEI = b"PK\x03\x04jei"
LIB = b"PK\x03\x04lib"


def _file(name, content):
    return {
        "url": f"https://cdn.modrinth.com/{name}",
        "filename": name,
        "primary": True,
        "hashes": {"sha512": hashlib.sha512(content).hexdigest()},
    }


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/search"):
        facets = json.loads(request.url.params["facets"])
        assert ["categories:forge"] in facets and ["versions:1.21"] in facets
        return httpx.Response(200, json={"hits": [{"project_id": "jei", "title": "JEI", "downloads": 5}]})
    if path.endswith("/project/jei"):
        return httpx.Response(200, json={"title": "JEI", "description": "Items"})
    if path.endswith("/project/lib"):
        return httpx.Response(200, json={"title": "Lib"})
    if path.endswith("/project/old"):
        return httpx.Response(200, json={"title": "Old"})
    if path.endswith("/project/jei/version"):
        return httpx.Response(200, json=[{
            "version_type": "release",
            "files": [_file("jei-forge.jar", JEI)],
            "dependencies": [{"project_id": "lib", "dependency_type": "required"},
                             {"project_id": "x", "dependency_type": "optional"}],
        }])
    if path.endswith("/project/lib/version"):
        return httpx.Response(200, json=[{"version_type": "release", "files": [_file("lib.jar", LIB)], "dependencies": []}])
    if path.endswith("/project/old/version"):
        return httpx.Response(200, json=[])
    if path == "/jei-forge.jar":
        return httpx.Response(200, content=JEI)
    if path == "/lib.jar":
        return httpx.Response(200, content=LIB)
    return httpx.Response(404)


@pytest.fixture(autouse=True)
def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "admin_password", TEST_PASSWORD)
    monkeypatch.setattr(settings, "admin_jwt_secret", "test-jwt-secret")
    monkeypatch.setattr(settings, "mods_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "public_base_url", "http://test.local")
    monkeypatch.setattr(
        modrinth_service, "_client",
        lambda: httpx.AsyncClient(base_url=modrinth_service.API_URL, transport=httpx.MockTransport(_handler)),
    )


async def _headers(client):
    resp = await client.post("/api/v1/admin/login", json={"password": TEST_PASSWORD})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    await client.put("/api/v1/admin/profile", headers=headers, json={
        "mc_version": "1.21", "loader": "forge", "loader_version": "51.0.33",
        "server_address": "mc.local", "server_port": 25565})
    return headers


async def test_search_filters_by_profile(client):
    headers = await _headers(client)
    resp = await client.get("/api/v1/admin/modrinth/search", params={"q": "jei"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()[0]["title"] == "JEI"


async def test_install_pulls_required_dependencies_once(client):
    headers = await _headers(client)
    body = {"project_id": "jei", "mod_type": "optional"}
    resp = await client.post("/api/v1/admin/modrinth/install", headers=headers, json=body)
    assert resp.status_code == 200
    installed = resp.json()["installed"]
    assert [m["file_name"] for m in installed] == ["jei-forge.jar", "lib.jar"]
    assert all(m["mod_type"] == "optional" and m["loader"] == "forge" and m["mc_version"] == "1.21" for m in installed)
    assert [m["modrinth_project_id"] for m in installed] == ["jei", "lib"]

    again = await client.post("/api/v1/admin/modrinth/install", headers=headers, json=body)
    assert again.json() == {"installed": [], "skipped": ["JEI", "Lib"]}


async def test_install_without_matching_version_is_404(client):
    headers = await _headers(client)
    resp = await client.post("/api/v1/admin/modrinth/install", headers=headers, json={"project_id": "old"})
    assert resp.status_code == 404
    assert "forge 1.21" in resp.json()["detail"]


async def test_modrinth_requires_admin(client):
    assert (await client.get("/api/v1/admin/modrinth/search")).status_code == 401
