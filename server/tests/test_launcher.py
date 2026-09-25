from app.schemas.launcher import LauncherVersionOut


async def test_version_endpoint_returns_service_result(client, mocker):
    mocker.patch(
        "app.api.v1.endpoints.launcher.launcher_service.get_latest_version",
        return_value=LauncherVersionOut(
            version="v1.2.0", download_url_windows="http://x/win.zip", download_url_macos="http://x/mac.zip"
        ),
    )

    resp = await client.get("/api/v1/launcher/version")

    assert resp.status_code == 200
    assert resp.json() == {
        "version": "v1.2.0",
        "download_url_windows": "http://x/win.zip",
        "download_url_macos": "http://x/mac.zip",
    }
