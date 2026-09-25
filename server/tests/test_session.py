SERVER_ID = "a" * 40


async def _register_and_login(client, username="Steve", password="pass1234"):
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
