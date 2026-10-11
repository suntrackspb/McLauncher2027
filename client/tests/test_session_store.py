from core.settings.session_store import SessionStore


def test_roundtrip_and_clear(tmp_path):
    store = SessionStore(tmp_path)
    assert store.load() is None

    session = {"username": "sun", "uuid": "a" * 32, "access_token": "b" * 32}
    store.save(session)
    assert SessionStore(tmp_path).load() == session

    store.clear()
    assert store.load() is None


def test_broken_file_is_ignored(tmp_path):
    (tmp_path / "session.json").write_text("{not json", encoding="utf-8")
    assert SessionStore(tmp_path).load() is None

    (tmp_path / "session.json").write_text('{"username": "sun"}', encoding="utf-8")
    assert SessionStore(tmp_path).load() is None
