import pytest

from core.api_client.client import ApiClient, ApiError


class FakeResponse:
    def __init__(self, status_code, json_body):
        self.status_code = status_code
        self._json_body = json_body
        self.text = str(json_body)

    def json(self):
        return self._json_body


def test_register_returns_json_on_success(mocker):
    mocker.patch("requests.Session.post", return_value=FakeResponse(201, {"status": "OK"}))
    client = ApiClient("http://localhost:8000")
    assert client.register("Steve", "pw") == {"status": "OK"}


def test_login_raises_api_error_on_forbidden(mocker):
    mocker.patch(
        "requests.Session.post",
        return_value=FakeResponse(403, {"detail": "Неверный логин или пароль"}),
    )
    client = ApiClient("http://localhost:8000")
    with pytest.raises(ApiError) as exc_info:
        client.login("Steve", "wrong")
    assert exc_info.value.status_code == 403
    assert "Неверный логин" in str(exc_info.value)


def test_network_error_wrapped_as_api_error(mocker):
    import requests

    mocker.patch("requests.Session.get", side_effect=requests.ConnectionError("boom"))
    client = ApiClient("http://localhost:8000")
    with pytest.raises(ApiError):
        client.get_required_mods("forge", "1.20.1")


def test_get_required_mods_passes_query_params(mocker):
    mock_get = mocker.patch("requests.Session.get", return_value=FakeResponse(200, []))
    client = ApiClient("http://localhost:8000")
    client.get_required_mods("forge", "1.20.1")
    _, kwargs = mock_get.call_args
    assert kwargs["params"] == {"loader": "forge", "mc_version": "1.20.1"}
