import hashlib

import pytest

from core.sync.downloader import DownloadIntegrityError, apply_sync_plan
from core.sync.mod_sync import ModEntry, SyncPlan

CONTENT = b"totally-a-jar-file"
HASH = hashlib.sha256(CONTENT).hexdigest()


class FakeStreamResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self._content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i : i + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeSession:
    def __init__(self, response: FakeStreamResponse):
        self._response = response
        self.requested_urls = []

    def get(self, url, stream, timeout):
        self.requested_urls.append(url)
        return self._response


def test_apply_sync_plan_downloads_and_verifies_hash(tmp_path):
    entry = ModEntry(id=1, name="JEI", file_name="jei.jar", url="https://x/jei.jar", file_hash=HASH, size=len(CONTENT))
    plan = SyncPlan(to_download=[entry], to_delete=[])
    session = FakeSession(FakeStreamResponse(CONTENT))

    apply_sync_plan(plan, tmp_path, session=session)

    assert (tmp_path / "jei.jar").read_bytes() == CONTENT
    assert not (tmp_path / "jei.jar.part").exists()
    assert session.requested_urls == ["https://x/jei.jar"]


def test_apply_sync_plan_deletes_stale_files(tmp_path):
    (tmp_path / "old_mod.jar").write_bytes(b"anything")
    plan = SyncPlan(to_download=[], to_delete=[tmp_path / "old_mod.jar"])

    apply_sync_plan(plan, tmp_path, session=FakeSession(FakeStreamResponse(b"")))

    assert not (tmp_path / "old_mod.jar").exists()


def test_apply_sync_plan_raises_on_hash_mismatch_and_cleans_up(tmp_path):
    entry = ModEntry(
        id=1, name="JEI", file_name="jei.jar", url="https://x/jei.jar", file_hash="0" * 64, size=len(CONTENT)
    )
    plan = SyncPlan(to_download=[entry], to_delete=[])
    session = FakeSession(FakeStreamResponse(CONTENT))

    with pytest.raises(DownloadIntegrityError):
        apply_sync_plan(plan, tmp_path, session=session)

    assert not (tmp_path / "jei.jar").exists()
    assert not (tmp_path / "jei.jar.part").exists()


def test_apply_sync_plan_reports_progress(tmp_path):
    entry = ModEntry(id=1, name="JEI", file_name="jei.jar", url="https://x/jei.jar", file_hash=HASH, size=len(CONTENT))
    plan = SyncPlan(to_download=[entry], to_delete=[])
    session = FakeSession(FakeStreamResponse(CONTENT))

    statuses = []
    progresses = []

    class Reporter:
        def status(self, message):
            statuses.append(message)

        def progress(self, current, maximum):
            progresses.append((current, maximum))

    apply_sync_plan(plan, tmp_path, reporter=Reporter(), session=session)

    assert any("JEI" in s for s in statuses)
    assert progresses[-1] == (len(CONTENT), len(CONTENT))
