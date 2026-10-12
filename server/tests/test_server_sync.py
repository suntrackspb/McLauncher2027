import secrets
import threading

import pytest
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

from app.core.config import settings
from tests.test_admin import TEST_PASSWORD

FTP_PASSWORD = secrets.token_urlsafe(8)
PATCHED = b"PK\x03\x04patched-authlib"
ORIGINAL = b"PK\x03\x04original-authlib"


@pytest.fixture
def ftp_root(tmp_path):
    root = tmp_path / "server"
    (root / "mods").mkdir(parents=True)
    (root / "mods" / "stray.jar").write_bytes(b"PK\x03\x04stray")
    lib = root / "libraries/com/mojang/authlib/6.0.54"
    lib.mkdir(parents=True)
    (lib / "authlib-6.0.54.jar").write_bytes(ORIGINAL)
    (root / "libraries/com/mojang/authlib/9.9.9").mkdir()
    return root


@pytest.fixture
def ftp_server(ftp_root):
    auth = DummyAuthorizer()
    auth.add_user("mc", FTP_PASSWORD, str(ftp_root), perm="elradfmwMT")
    handler = type("H", (FTPHandler,), {"authorizer": auth})
    server = FTPServer(("127.0.0.1", 0), handler)
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            server.serve_forever(timeout=0.05, blocking=False)
        server.close_all()

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    yield server.address[1]
    stop.set()
    thread.join(2)


@pytest.fixture(autouse=True)
def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "admin_password", TEST_PASSWORD)
    monkeypatch.setattr(settings, "admin_jwt_secret", "test-jwt-secret")
    monkeypatch.setattr(settings, "connection_secret", "test-connection-secret")
    monkeypatch.setattr(settings, "mods_storage_dir", str(tmp_path / "mods-storage"))
    authlib_dir = tmp_path / "authlib-storage"
    authlib_dir.mkdir()
    (authlib_dir / "authlib-6.0.54_skinfix.jar").write_bytes(PATCHED)
    monkeypatch.setattr(settings, "authlib_storage_dir", str(authlib_dir))
    monkeypatch.setattr(settings, "public_base_url", "http://test.local")


async def _admin(client):
    resp = await client.post("/api/v1/admin/login", json={"password": TEST_PASSWORD})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    await client.put("/api/v1/admin/profile", headers=headers, json={
        "mc_version": "1.21", "loader": "forge", "loader_version": "51.0.33",
        "server_address": "mc.local", "server_port": 25565})
    for name, server_side in (("tree.jar", "true"), ("minimap.jar", "false")):
        await client.post("/api/v1/admin/mods", headers=headers,
            data={"name": name, "mod_type": "required", "loader": "forge", "mc_version": "1.21", "server_side": server_side},
            files={"file": (name, b"PK\x03\x04" + name.encode(), "application/java-archive")})
    return headers


async def _connect(client, headers, port, **extra):
    body = {"protocol": "ftp", "host": "127.0.0.1", "port": port, "username": "mc",
            "password": FTP_PASSWORD, "server_dir": "/", **extra}
    return await client.put("/api/v1/admin/server/connection", headers=headers, json=body)


async def test_connection_hides_secrets_and_keeps_them(client, ftp_server):
    headers = await _admin(client)
    resp = await _connect(client, headers, ftp_server)
    assert resp.json()["has_password"] is True
    assert "password" not in resp.json()
    # password=None — сохранённый пароль остаётся рабочим
    await _connect(client, headers, ftp_server, password=None)
    test = await client.post("/api/v1/admin/server/connection/test", headers=headers)
    assert test.status_code == 200
    assert test.json()["mods_dir"] is True and test.json()["libraries_dir"] is True


async def test_wrong_password_is_502(client, ftp_server):
    headers = await _admin(client)
    await _connect(client, headers, ftp_server, password="wrong")
    resp = await client.post("/api/v1/admin/server/connection/test", headers=headers)
    assert resp.status_code == 502


async def test_sync_plan_then_apply(client, ftp_server, ftp_root):
    headers = await _admin(client)
    await _connect(client, headers, ftp_server)

    plan = (await client.get("/api/v1/admin/server/sync", headers=headers)).json()
    assert plan["mods_upload"] == ["tree.jar"]  # minimap — только клиент
    assert plan["mods_remove"] == ["stray.jar"]
    assert plan["authlib"] == {"6.0.54": "to_patch", "9.9.9": "no_patch"}
    assert (ftp_root / "mods" / "stray.jar").exists()  # план ничего не трогает

    result = (await client.post("/api/v1/admin/server/sync", headers=headers)).json()
    assert result["authlib"]["6.0.54"] == "patched"
    assert sorted(p.name for p in (ftp_root / "mods").iterdir()) == ["tree.jar"]
    assert (ftp_root / result["backup_dir"] / "stray.jar").exists()
    lib = ftp_root / "libraries/com/mojang/authlib/6.0.54"
    assert (lib / "authlib-6.0.54.jar").read_bytes() == PATCHED
    assert (lib / "authlib-6.0.54.jar.orig").read_bytes() == ORIGINAL

    again = (await client.get("/api/v1/admin/server/sync", headers=headers)).json()
    assert again["mods_upload"] == [] and again["mods_remove"] == []
    assert again["mods_ok"] == ["tree.jar"] and again["authlib"]["6.0.54"] == "patched"


async def test_sync_without_connection_is_409(client):
    headers = await _admin(client)
    assert (await client.get("/api/v1/admin/server/sync", headers=headers)).status_code == 409
