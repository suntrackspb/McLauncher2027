async def test_register_and_login(client):
    resp = await client.post("/api/v1/auth/register", json={"username": "TaoGunner", "password": "hunter2"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "taogunner"
    assert len(body["uuid"]) == 32

    resp = await client.post("/api/v1/auth/login", json={"username": "TaoGunner", "password": "hunter2"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["UUID"] == body["UUID"]  # alias present
    assert len(body["accessToken"]) == 32


async def test_register_duplicate_username(client):
    payload = {"username": "Notch", "password": "apple123"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 400


async def test_login_wrong_password(client):
    await client.post("/api/v1/auth/register", json={"username": "Notch", "password": "apple123"})
    resp = await client.post("/api/v1/auth/login", json={"username": "Notch", "password": "wrong"})
    assert resp.status_code == 403


async def test_register_invalid_username(client):
    resp = await client.post("/api/v1/auth/register", json={"username": "a", "password": "apple123"})
    assert resp.status_code == 400
