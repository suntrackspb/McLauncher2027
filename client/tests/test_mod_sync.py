import hashlib

from core.sync.mod_sync import plan_sync

REQUIRED_MOD = {
    "id": 1,
    "name": "JEI",
    "file_name": "jei.jar",
    "url": "https://example.com/jei.jar",
    "file_hash": hashlib.sha256(b"jei-content").hexdigest(),
    "size": 11,
}
OPTIONAL_MOD = {
    "id": 2,
    "name": "OptiFine",
    "file_name": "optifine.jar",
    "url": "https://example.com/optifine.jar",
    "file_hash": hashlib.sha256(b"optifine-content").hexdigest(),
    "size": 16,
}


def test_missing_required_mod_is_downloaded(tmp_path):
    plan = plan_sync([REQUIRED_MOD], [], set(), tmp_path)
    assert [m.file_name for m in plan.to_download] == ["jei.jar"]
    assert plan.to_delete == []


def test_up_to_date_required_mod_is_not_redownloaded(tmp_path):
    (tmp_path / "jei.jar").write_bytes(b"jei-content")
    plan = plan_sync([REQUIRED_MOD], [], set(), tmp_path)
    assert plan.to_download == []


def test_stale_hash_triggers_redownload(tmp_path):
    (tmp_path / "jei.jar").write_bytes(b"old-content")
    plan = plan_sync([REQUIRED_MOD], [], set(), tmp_path)
    assert [m.file_name for m in plan.to_download] == ["jei.jar"]


def test_leftover_file_is_deleted(tmp_path):
    (tmp_path / "jei.jar").write_bytes(b"jei-content")
    (tmp_path / "removed_mod.jar").write_bytes(b"anything")
    plan = plan_sync([REQUIRED_MOD], [], set(), tmp_path)
    assert plan.to_delete == [tmp_path / "removed_mod.jar"]


def test_disabled_optional_mod_is_not_downloaded_and_is_deleted_if_present(tmp_path):
    (tmp_path / "optifine.jar").write_bytes(b"optifine-content")
    plan = plan_sync([], [OPTIONAL_MOD], set(), tmp_path)
    assert plan.to_download == []
    assert plan.to_delete == [tmp_path / "optifine.jar"]


def test_enabled_optional_mod_is_downloaded_and_kept(tmp_path):
    plan = plan_sync([], [OPTIONAL_MOD], {2}, tmp_path)
    assert [m.file_name for m in plan.to_download] == ["optifine.jar"]

    (tmp_path / "optifine.jar").write_bytes(b"optifine-content")
    plan = plan_sync([], [OPTIONAL_MOD], {2}, tmp_path)
    assert plan.to_download == []
    assert plan.to_delete == []


def test_missing_mods_dir_is_treated_as_empty(tmp_path):
    missing_dir = tmp_path / "does-not-exist"
    plan = plan_sync([REQUIRED_MOD], [], set(), missing_dir)
    assert [m.file_name for m in plan.to_download] == ["jei.jar"]
    assert plan.to_delete == []
