from core.launch.servers_dat import write_server_bookmark

# Эталон NBT, собранный вручную по формату servers.dat:
# compound "" { list "servers" [ compound { string name, string ip } ] }
EXPECTED = (
    b"\x0a\x00\x00"
    b"\x09\x00\x07servers" b"\x0a\x00\x00\x00\x01"
    b"\x08\x00\x04name" b"\x00\x08New Year"
    b"\x08\x00\x02ip" b"\x00\x0dmc.example.ru"
    b"\x00"
    b"\x00"
)


def test_writes_single_server_entry(tmp_path):
    write_server_bookmark(tmp_path, "New Year", "mc.example.ru")
    assert (tmp_path / "servers.dat").read_bytes() == EXPECTED


def test_overwrites_previous_list(tmp_path):
    (tmp_path / "servers.dat").write_bytes(b"old servers list")
    write_server_bookmark(tmp_path, "New Year", "mc.example.ru")
    assert (tmp_path / "servers.dat").read_bytes() == EXPECTED


def test_creates_missing_directory(tmp_path):
    write_server_bookmark(tmp_path / "minecraft", "New Year", "mc.example.ru")
    assert (tmp_path / "minecraft" / "servers.dat").exists()
