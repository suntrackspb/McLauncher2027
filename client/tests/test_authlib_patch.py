from unittest.mock import MagicMock

from core.launch.authlib_patch import find_authlib_jars, patch_authlib_jars


def _make_authlib_jar(mc_dir, version: str, content: bytes) -> None:
    lib_dir = mc_dir / "libraries" / "com" / "mojang" / "authlib" / version
    lib_dir.mkdir(parents=True, exist_ok=True)
    (lib_dir / f"authlib-{version}.jar").write_bytes(content)


def _api_client_with_jars(jars: list[dict]) -> MagicMock:
    api_client = MagicMock()
    api_client.get_authlib_jars.return_value = jars
    return api_client


def test_find_authlib_jars_locates_installed_versions(tmp_path):
    _make_authlib_jar(tmp_path, "3.11.49", b"original")
    _make_authlib_jar(tmp_path, "6.0.54", b"original")

    found = find_authlib_jars(tmp_path)

    assert {p.name for p in found} == {"authlib-3.11.49.jar", "authlib-6.0.54.jar"}


def test_find_authlib_jars_returns_empty_when_not_installed(tmp_path):
    assert find_authlib_jars(tmp_path) == []


def test_patch_downloads_and_replaces_matching_version(tmp_path, mocker):
    mc_dir = tmp_path / "mc"
    cache_dir = tmp_path / "cache"
    _make_authlib_jar(mc_dir, "3.11.49", b"original-bytes")

    api_client = _api_client_with_jars(
        [{"version": "3.11.49", "url": "http://backend.example/authlib-files/authlib-3.11.49_skinfix.jar"}]
    )
    response = MagicMock(content=b"patched-bytes-with-our-url")
    response.raise_for_status.return_value = None
    mock_get = mocker.patch("core.launch.authlib_patch.requests.get", return_value=response)

    patched = patch_authlib_jars(mc_dir, api_client, cache_dir)

    target = mc_dir / "libraries" / "com" / "mojang" / "authlib" / "3.11.49" / "authlib-3.11.49.jar"
    assert patched == [target]
    assert target.read_bytes() == b"patched-bytes-with-our-url"
    assert (cache_dir / "authlib-3.11.49_skinfix.jar").read_bytes() == b"patched-bytes-with-our-url"
    mock_get.assert_called_once()


def test_patch_uses_cached_file_without_downloading_again(tmp_path, mocker):
    mc_dir = tmp_path / "mc"
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    _make_authlib_jar(mc_dir, "3.11.49", b"original-bytes")
    (cache_dir / "authlib-3.11.49_skinfix.jar").write_bytes(b"already-cached")

    api_client = _api_client_with_jars(
        [{"version": "3.11.49", "url": "http://backend.example/authlib-files/authlib-3.11.49_skinfix.jar"}]
    )
    mock_get = mocker.patch("core.launch.authlib_patch.requests.get")

    patched = patch_authlib_jars(mc_dir, api_client, cache_dir)

    target = mc_dir / "libraries" / "com" / "mojang" / "authlib" / "3.11.49" / "authlib-3.11.49.jar"
    assert patched == [target]
    assert target.read_bytes() == b"already-cached"
    mock_get.assert_not_called()


def test_patch_skips_version_without_prepared_replacement(tmp_path, mocker):
    mc_dir = tmp_path / "mc"
    cache_dir = tmp_path / "cache"
    _make_authlib_jar(mc_dir, "9.9.99", b"original-bytes")

    api_client = _api_client_with_jars([])
    mock_get = mocker.patch("core.launch.authlib_patch.requests.get")

    patched = patch_authlib_jars(mc_dir, api_client, cache_dir)

    target = mc_dir / "libraries" / "com" / "mojang" / "authlib" / "9.9.99" / "authlib-9.9.99.jar"
    assert patched == []
    assert target.read_bytes() == b"original-bytes"
    mock_get.assert_not_called()


def test_patch_handles_multiple_versions_independently(tmp_path, mocker):
    mc_dir = tmp_path / "mc"
    cache_dir = tmp_path / "cache"
    _make_authlib_jar(mc_dir, "3.11.49", b"original-a")
    _make_authlib_jar(mc_dir, "6.0.54", b"original-b")
    # Для 6.0.54 заготовки на сервере нет — должна остаться нетронутой.

    api_client = _api_client_with_jars(
        [{"version": "3.11.49", "url": "http://backend.example/authlib-files/authlib-3.11.49_skinfix.jar"}]
    )
    response = MagicMock(content=b"patched-a")
    response.raise_for_status.return_value = None
    mocker.patch("core.launch.authlib_patch.requests.get", return_value=response)

    patched = patch_authlib_jars(mc_dir, api_client, cache_dir)

    assert len(patched) == 1
    assert patched[0].name == "authlib-3.11.49.jar"
    a = mc_dir / "libraries" / "com" / "mojang" / "authlib" / "3.11.49" / "authlib-3.11.49.jar"
    b = mc_dir / "libraries" / "com" / "mojang" / "authlib" / "6.0.54" / "authlib-6.0.54.jar"
    assert a.read_bytes() == b"patched-a"
    assert b.read_bytes() == b"original-b"
