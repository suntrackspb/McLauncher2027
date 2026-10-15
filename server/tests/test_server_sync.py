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


# --- этап 2: управление, лог, RCON -------------------------------------------

import socket
import struct

from app.services import server_control_service


def test_set_properties_keeps_comments_and_order():
    text = "#Minecraft\nmotd=hi\nenable-rcon=false\n"
    out = server_control_service.set_properties(text, {"enable-rcon": "true", "rcon.port": "25575"})
    assert out == "#Minecraft\nmotd=hi\nenable-rcon=true\nrcon.port=25575\n"
    assert server_control_service.parse_properties(out)["enable-rcon"] == "true"


@pytest.fixture
def rcon_server():
    """Фейковый RCON: пароль "secret", на любую команду отвечает "ok: <cmd>"."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen()

    def recv(conn):
        (n,) = struct.unpack("<i", conn.recv(4))
        data = b""
        while len(data) < n:
            data += conn.recv(n - len(data))
        rid, kind = struct.unpack("<ii", data[:8])
        return rid, data[8:-2].decode()

    def send(conn, rid, body):
        payload = struct.pack("<ii", rid, 0) + body.encode() + b"\x00\x00"
        conn.sendall(struct.pack("<i", len(payload)) + payload)

    def serve():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            with conn:
                rid, pwd = recv(conn)
                send(conn, rid if pwd == "secret" else -1, "")
                if pwd != "secret":
                    continue
                rid, cmd = recv(conn)
                send(conn, rid, f"ok: {cmd}")

    threading.Thread(target=serve, daemon=True).start()
    yield srv.getsockname()[1]
    srv.close()


async def test_ftp_status_log_and_rcon(client, ftp_server, ftp_root, rcon_server):
    headers = await _admin(client)
    await client.put("/api/v1/admin/profile", headers=headers, json={
        "mc_version": "1.21", "loader": "forge", "loader_version": "51.0.33",
        "server_address": "127.0.0.1", "server_port": 25565})
    # service_name для FTP игнорируется — управлять запуском по FTP нельзя
    resp = await _connect(client, headers, ftp_server, service_name="mc-forge")
    assert resp.json()["service_name"] is None
    (ftp_root / "server.properties").write_text(f"#c\nenable-rcon=false\nrcon.port={rcon_server}\n")
    (ftp_root / "logs").mkdir()
    (ftp_root / "logs" / "latest.log").write_text("\n".join(f"line {i}" for i in range(50)))

    status = (await client.get("/api/v1/admin/server/status", headers=headers)).json()
    assert status["can_control"] is False and status["service_state"] is None
    assert status["rcon_enabled"] is False

    log = (await client.get("/api/v1/admin/server/log", params={"lines": 3}, headers=headers)).json()
    assert log["lines"] == ["line 47", "line 48", "line 49"]

    assert (await client.post("/api/v1/admin/server/control/restart", headers=headers)).status_code == 409
    assert (await client.post("/api/v1/admin/server/rcon", headers=headers, json={"command": "list"})).status_code == 409

    assert (await client.post("/api/v1/admin/server/rcon/enable", headers=headers)).json()["needs_restart"] is True
    props = server_control_service.parse_properties((ftp_root / "server.properties").read_text())
    assert props["enable-rcon"] == "true" and props["rcon.port"] == str(rcon_server) and props["rcon.password"]

    # подставляем пароль, который знает фейковый RCON
    (ftp_root / "server.properties").write_text(f"enable-rcon=true\nrcon.port={rcon_server}\nrcon.password=secret\n")
    out = await client.post("/api/v1/admin/server/rcon", headers=headers, json={"command": "say hi"})
    assert out.json() == {"output": "ok: say hi"}
    status = (await client.get("/api/v1/admin/server/status", headers=headers)).json()
    assert status["rcon_enabled"] is True and status["players"] == "ok: list"

    (ftp_root / "server.properties").write_text(f"enable-rcon=true\nrcon.port={rcon_server}\nrcon.password=bad\n")
    bad = await client.post("/api/v1/admin/server/rcon", headers=headers, json={"command": "list"})
    assert bad.status_code == 502 and "пароль" in bad.json()["detail"]


async def test_apply_rejects_stale_plan(client, ftp_server, ftp_root):
    headers = await _admin(client)
    await _connect(client, headers, ftp_server)
    plan = (await client.get("/api/v1/admin/server/sync", headers=headers)).json()
    assert plan["plan_id"]
    (ftp_root / "mods" / "new-stray.jar").write_bytes(b"PK\x03\x04x")  # сервер изменился
    resp = await client.post("/api/v1/admin/server/sync", headers=headers, json={"plan_id": plan["plan_id"]})
    assert resp.status_code == 409
    assert (ftp_root / "mods" / "stray.jar").exists()  # ничего не применилось
    fresh = (await client.get("/api/v1/admin/server/sync", headers=headers)).json()
    ok = await client.post("/api/v1/admin/server/sync", headers=headers, json={"plan_id": fresh["plan_id"]})
    assert ok.status_code == 200 and ok.json()["applied"] is True


def test_properties_escaping_roundtrip():
    text = "#c\nmotd=A Minecraft Server\\u0021\nlevel-name=world\n"
    assert server_control_service.parse_properties(text)["motd"] == "A Minecraft Server!"
    out = server_control_service.set_properties(text, {"motd": "Привет: мир=1"})
    assert "Привет" not in out  # не-ASCII уходит в \uXXXX
    assert server_control_service.parse_properties(out)["motd"] == "Привет: мир=1"


async def test_ftp_properties_edit(client, ftp_server, ftp_root):
    headers = await _admin(client)
    await _connect(client, headers, ftp_server)
    (ftp_root / "server.properties").write_text("#c\npvp=true\nmotd=hi\n")
    got = (await client.get("/api/v1/admin/server/properties", headers=headers)).json()
    assert got["exists"] is True and got["values"] == {"pvp": "true", "motd": "hi"}

    resp = await client.put("/api/v1/admin/server/properties", headers=headers,
                            json={"updates": {"pvp": "false", "max-players": "10"}})
    assert resp.json()["values"]["max-players"] == "10"
    assert (ftp_root / "server.properties").read_text() == "#c\npvp=false\nmotd=hi\nmax-players=10\n"

    bad = await client.put("/api/v1/admin/server/properties", headers=headers, json={"updates": {"motd": "a\nb"}})
    assert bad.status_code == 400
