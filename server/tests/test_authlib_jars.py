from app.core.config import settings


async def test_authlib_jars_empty_when_storage_dir_empty(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "authlib_storage_dir", str(tmp_path))
    resp = await client.get("/api/v1/launcher/authlib-jars")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_authlib_jars_lists_matching_files_only(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "authlib_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "public_base_url", "http://backend.example")

    (tmp_path / "authlib-4.0.43_skinfix.jar").write_bytes(b"fake jar")
    (tmp_path / "authlib-6.0.54_skinfix.jar").write_bytes(b"fake jar")
    (tmp_path / "readme.txt").write_text("not a jar")

    resp = await client.get("/api/v1/launcher/authlib-jars")
    assert resp.status_code == 200
    assert resp.json() == [
        {"version": "4.0.43", "url": "http://backend.example/authlib-files/authlib-4.0.43_skinfix.jar"},
        {"version": "6.0.54", "url": "http://backend.example/authlib-files/authlib-6.0.54_skinfix.jar"},
    ]
