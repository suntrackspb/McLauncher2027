import zipfile

from updater.app_updater import extract_new_version, replace_launcher, run


def _make_zip_with(zip_path, *, entries: dict[str, bytes]):
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)


def test_extract_new_version_finds_exe_on_windows_style_path(tmp_path):
    zip_path = tmp_path / "update.zip"
    _make_zip_with(zip_path, entries={"NewLauncher.exe": b"binary"})

    result = extract_new_version(zip_path, tmp_path / "extract", tmp_path / "Launcher.exe")

    assert result.name == "NewLauncher.exe"


def test_extract_new_version_finds_app_bundle_on_macos_style_path(tmp_path):
    zip_path = tmp_path / "update.zip"
    _make_zip_with(zip_path, entries={"NewLauncher.app/Contents/MacOS/launcher": b"binary"})

    result = extract_new_version(zip_path, tmp_path / "extract", tmp_path / "Launcher.app")

    assert result.name == "NewLauncher.app"
    assert result.is_dir()


def test_extract_new_version_raises_when_nothing_found(tmp_path):
    zip_path = tmp_path / "update.zip"
    _make_zip_with(zip_path, entries={"readme.txt": b"hi"})

    try:
        extract_new_version(zip_path, tmp_path / "extract", tmp_path / "Launcher.exe")
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass


def test_replace_launcher_swaps_single_file(tmp_path):
    launcher_path = tmp_path / "Launcher.exe"
    launcher_path.write_bytes(b"old")
    new_path = tmp_path / "NewLauncher.exe"
    new_path.write_bytes(b"new")

    replace_launcher(launcher_path, new_path)

    assert launcher_path.read_bytes() == b"new"
    assert not (tmp_path / "Launcher.exe.old").exists()


def test_replace_launcher_swaps_app_bundle_directory(tmp_path):
    launcher_path = tmp_path / "Launcher.app"
    (launcher_path / "Contents" / "MacOS").mkdir(parents=True)
    (launcher_path / "Contents" / "MacOS" / "launcher").write_bytes(b"old")

    new_path = tmp_path / "NewLauncher.app"
    (new_path / "Contents" / "MacOS").mkdir(parents=True)
    (new_path / "Contents" / "MacOS" / "launcher").write_bytes(b"new")

    replace_launcher(launcher_path, new_path)

    assert (launcher_path / "Contents" / "MacOS" / "launcher").read_bytes() == b"new"
    assert not (tmp_path / "Launcher.app.old").exists()


def test_run_returns_false_when_launcher_does_not_close(mocker, tmp_path):
    mocker.patch("updater.app_updater.wait_for_launcher_close", return_value=False)
    assert run(str(tmp_path / "Launcher.exe"), "http://example.com/update.zip") is False


def test_run_happy_path_calls_all_steps_in_order(mocker, tmp_path):
    launcher_path = tmp_path / "Launcher.exe"
    launcher_path.write_bytes(b"old")

    mocker.patch("updater.app_updater.wait_for_launcher_close", return_value=True)
    mocker.patch("updater.app_updater.download_archive")
    new_path = tmp_path / "extracted" / "New.exe"
    new_path.parent.mkdir(parents=True)
    new_path.write_bytes(b"new")
    mocker.patch("updater.app_updater.extract_new_version", return_value=new_path)
    relaunch_mock = mocker.patch("updater.app_updater.relaunch")

    assert run(str(launcher_path), "http://example.com/update.zip") is True
    assert launcher_path.read_bytes() == b"new"
    relaunch_mock.assert_called_once()
