import zipfile

from updater.app_updater import extract_new_version, relaunch, replace_launcher, run


def _make_zip_with(zip_path, *, entries: dict[str, bytes]):
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)


def test_extract_new_version_finds_onedir_folder_on_windows_style_path(tmp_path):
    zip_path = tmp_path / "update.zip"
    _make_zip_with(
        zip_path,
        entries={
            "McLauncher2027/McLauncher2027.exe": b"binary",
            "McLauncher2027/some_dependency.dll": b"dll",
        },
    )

    # launcher_path — уже resolve_launcher_path'ом приведённая директория
    # (не .exe), как это реально приходит из ui_bridge/api.py.
    result = extract_new_version(zip_path, tmp_path / "extract", tmp_path / "Launcher")

    assert result.name == "McLauncher2027"
    assert result.is_dir()
    assert (result / "some_dependency.dll").exists()


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
        extract_new_version(zip_path, tmp_path / "extract", tmp_path / "Launcher")
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass


def test_replace_launcher_swaps_onedir_folder(tmp_path):
    launcher_path = tmp_path / "Launcher"
    launcher_path.mkdir()
    (launcher_path / "Launcher.exe").write_bytes(b"old")

    new_path = tmp_path / "NewLauncher"
    new_path.mkdir()
    (new_path / "Launcher.exe").write_bytes(b"new")

    replace_launcher(launcher_path, new_path)

    assert (launcher_path / "Launcher.exe").read_bytes() == b"new"
    assert not (tmp_path / "Launcher.old").exists()


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


def test_relaunch_finds_exe_inside_windows_onedir_folder(mocker, tmp_path):
    mocker.patch("updater.app_updater.platform.system", return_value="Windows")
    launcher_path = tmp_path / "Launcher"
    launcher_path.mkdir()
    (launcher_path / "Launcher.exe").write_bytes(b"exe")
    popen_mock = mocker.patch("updater.app_updater.subprocess.Popen")

    relaunch(launcher_path)

    popen_mock.assert_called_once()
    called_args = popen_mock.call_args[0][0]
    assert called_args[0] == str(launcher_path / "Launcher.exe")


def test_relaunch_opens_macos_bundle_with_open_command(mocker, tmp_path):
    launcher_path = tmp_path / "Launcher.app"
    launcher_path.mkdir()
    popen_mock = mocker.patch("updater.app_updater.subprocess.Popen")

    relaunch(launcher_path)

    popen_mock.assert_called_once_with(["open", str(launcher_path)])


def test_run_returns_false_when_launcher_does_not_close(mocker, tmp_path):
    mocker.patch("updater.app_updater.wait_for_launcher_close", return_value=False)
    assert run(str(tmp_path / "Launcher"), "http://example.com/update.zip") is False


def test_run_happy_path_calls_all_steps_in_order(mocker, tmp_path):
    launcher_path = tmp_path / "Launcher"
    launcher_path.mkdir()
    (launcher_path / "Launcher.exe").write_bytes(b"old")

    mocker.patch("updater.app_updater.wait_for_launcher_close", return_value=True)
    mocker.patch("updater.app_updater.download_archive")
    new_path = tmp_path / "extracted" / "New"
    new_path.mkdir(parents=True)
    (new_path / "New.exe").write_bytes(b"new")
    mocker.patch("updater.app_updater.extract_new_version", return_value=new_path)
    relaunch_mock = mocker.patch("updater.app_updater.relaunch")

    assert run(str(launcher_path), "http://example.com/update.zip") is True
    assert (launcher_path / "New.exe").read_bytes() == b"new"
    relaunch_mock.assert_called_once()
