from app.models.mod import Mod, ModType


async def _add_mod(db_session, *, mod_type, loader="forge", mc_version="1.20.1", name="TestMod"):
    mod = Mod(
        name=name,
        description="desc",
        file_name=f"{name}.jar",
        url=f"https://example.com/{name}.jar",
        file_hash="a" * 64,
        size=1024,
        mod_type=mod_type,
        loader=loader,
        mc_version=mc_version,
    )
    db_session.add(mod)
    await db_session.commit()


async def test_manifest_returns_only_required_mods_for_loader_and_version(client, db_session):
    await _add_mod(db_session, mod_type=ModType.required, name="Required1")
    await _add_mod(db_session, mod_type=ModType.optional, name="Optional1")
    await _add_mod(db_session, mod_type=ModType.required, loader="fabric", name="OtherLoader")

    resp = await client.get("/api/v1/mods/manifest", params={"loader": "forge", "mc_version": "1.20.1"})
    assert resp.status_code == 200
    names = [m["name"] for m in resp.json()]
    assert names == ["Required1"]


async def test_optional_endpoint_returns_only_optional_mods(client, db_session):
    await _add_mod(db_session, mod_type=ModType.required, name="Required1")
    await _add_mod(db_session, mod_type=ModType.optional, name="Optional1")

    resp = await client.get("/api/v1/mods/optional", params={"loader": "forge", "mc_version": "1.20.1"})
    assert resp.status_code == 200
    names = [m["name"] for m in resp.json()]
    assert names == ["Optional1"]
