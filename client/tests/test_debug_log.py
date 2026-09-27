from core.debug_log import DebugLogger, is_debug_flag_set


def test_disabled_logger_does_not_create_file(tmp_path, mocker):
    mocker.patch("core.debug_log.debug_log_path", return_value=tmp_path / "debug.log")
    logger = DebugLogger(enabled=False)

    logger.log("hello")
    logger.log_block("title", {"a": 1})

    assert not (tmp_path / "debug.log").exists()


def test_enabled_logger_writes_messages_and_blocks(tmp_path, mocker):
    log_path = tmp_path / "debug.log"
    mocker.patch("core.debug_log.debug_log_path", return_value=log_path)
    logger = DebugLogger(enabled=True)

    logger.log("hello world")
    logger.log_block("options", {"a": 1, "b": [1, 2]})

    content = log_path.read_text(encoding="utf-8")
    assert "hello world" in content
    assert "options:" in content
    assert '"a": 1' in content


def test_is_debug_flag_set_reads_argv(mocker):
    mocker.patch("sys.argv", ["app.py"])
    assert is_debug_flag_set() is False

    mocker.patch("sys.argv", ["app.py", "--debug"])
    assert is_debug_flag_set() is True
