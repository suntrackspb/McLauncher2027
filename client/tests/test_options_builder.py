from core.launch.options_builder import ServerProfile, build_jvm_arguments, build_launch_options
from core.settings.store import LauncherSettings


def test_build_jvm_arguments_includes_heap_size():
    args = build_jvm_arguments(6144)
    assert "-Xmx6144M" in args
    assert any(a.startswith("-Xms") for a in args)


def test_build_jvm_arguments_caps_xms_for_small_heap():
    args = build_jvm_arguments(512)
    assert "-Xms512M" in args


def test_build_launch_options_maps_all_fields():
    settings = LauncherSettings(ram_mb=4096, resolution_width=1920, resolution_height=1080)
    profile = ServerProfile(
        mc_version="1.20.1",
        loader="forge",
        loader_version="47.4.13",
        server_address="mc.example.com",
        server_port=25565,
    )

    options = build_launch_options(
        username="Steve",
        uuid="a" * 32,
        access_token="b" * 32,
        settings=settings,
        profile=profile,
        minecraft_directory="/tmp/mc",
    )

    assert options["username"] == "Steve"
    assert options["uuid"] == "a" * 32
    assert options["token"] == "b" * 32
    assert options["server"] == "mc.example.com"
    assert options["port"] == "25565"
    assert options["resolutionWidth"] == "1920"
    assert options["resolutionHeight"] == "1080"
    assert options["customResolution"] is True
    assert options["gameDirectory"] == "/tmp/mc"
    assert "-Xmx4096M" in options["jvmArguments"]
