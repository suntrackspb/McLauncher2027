from core.launch.authlib_patch import find_authlib_jars, patch_authlib_jars


def _make_authlib_jar(mc_dir, version: str, content: bytes) -> None:
    lib_dir = mc_dir / "libraries" / "com" / "mojang" / "authlib" / version
    lib_dir.mkdir(parents=True, exist_ok=True)
    (lib_dir / f"authlib-{version}.jar").write_bytes(content)


def test_find_authlib_jars_locates_installed_versions(tmp_path):
    _make_authlib_jar(tmp_path, "3.11.49", b"original")
    _make_authlib_jar(tmp_path, "6.0.54", b"original")

    found = find_authlib_jars(tmp_path)

    assert {p.name for p in found} == {"authlib-3.11.49.jar", "authlib-6.0.54.jar"}


def test_find_authlib_jars_returns_empty_when_not_installed(tmp_path):
    assert find_authlib_jars(tmp_path) == []


def test_patch_replaces_matching_version_with_patched_jar(tmp_path):
    mc_dir = tmp_path / "mc"
    patched_dir = tmp_path / "patched"
    patched_dir.mkdir()

    _make_authlib_jar(mc_dir, "3.11.49", b"original-bytes")
    (patched_dir / "authlib-3.11.49_skinfix.jar").write_bytes(b"patched-bytes-with-our-url")

    patched = patch_authlib_jars(mc_dir, patched_dir)

    target = mc_dir / "libraries" / "com" / "mojang" / "authlib" / "3.11.49" / "authlib-3.11.49.jar"
    assert patched == [target]
    assert target.read_bytes() == b"patched-bytes-with-our-url"


def test_patch_skips_version_without_prepared_replacement(tmp_path):
    mc_dir = tmp_path / "mc"
    patched_dir = tmp_path / "patched"
    patched_dir.mkdir()

    _make_authlib_jar(mc_dir, "9.9.99", b"original-bytes")

    patched = patch_authlib_jars(mc_dir, patched_dir)

    target = mc_dir / "libraries" / "com" / "mojang" / "authlib" / "9.9.99" / "authlib-9.9.99.jar"
    assert patched == []
    assert target.read_bytes() == b"original-bytes"


def test_patch_handles_multiple_versions_independently(tmp_path):
    mc_dir = tmp_path / "mc"
    patched_dir = tmp_path / "patched"
    patched_dir.mkdir()

    _make_authlib_jar(mc_dir, "3.11.49", b"original-a")
    _make_authlib_jar(mc_dir, "6.0.54", b"original-b")
    (patched_dir / "authlib-3.11.49_skinfix.jar").write_bytes(b"patched-a")
    # Для 6.0.54 заготовки нет — должна остаться нетронутой.

    patched = patch_authlib_jars(mc_dir, patched_dir)

    assert len(patched) == 1
    assert patched[0].name == "authlib-3.11.49.jar"
    a = mc_dir / "libraries" / "com" / "mojang" / "authlib" / "3.11.49" / "authlib-3.11.49.jar"
    b = mc_dir / "libraries" / "com" / "mojang" / "authlib" / "6.0.54" / "authlib-6.0.54.jar"
    assert a.read_bytes() == b"patched-a"
    assert b.read_bytes() == b"original-b"
