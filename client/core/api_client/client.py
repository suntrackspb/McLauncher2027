import base64
import json
from urllib.parse import urljoin

import requests


class ApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ApiClient:
    """HTTP-клиент к McLauncher2027 backend (server/app/api/v1). Единственная точка,
    которая знает про сетевой контракт — остальной core с requests не работает
    напрямую, чтобы sync/loaders можно было тестировать без сети."""

    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

    def register(self, username: str, password: str) -> dict:
        return self._post(
            "/api/v1/auth/register", {"username": username, "password": password}, expected=201
        )

    def login(self, username: str, password: str) -> dict:
        return self._post(
            "/api/v1/auth/login", {"username": username, "password": password}, expected=200
        )

    def get_required_mods(self, loader: str, mc_version: str) -> list[dict]:
        return self._get("/api/v1/mods/manifest", {"loader": loader, "mc_version": mc_version})

    def get_optional_mods(self, loader: str, mc_version: str) -> list[dict]:
        return self._get("/api/v1/mods/optional", {"loader": loader, "mc_version": mc_version})

    def get_launcher_version(self) -> dict:
        return self._get_dict("/api/v1/launcher/version")

    def get_profile(self) -> dict:
        return self._get_dict("/api/v1/launcher/profile")

    def get_authlib_jars(self) -> list[dict]:
        return self._get("/api/v1/launcher/authlib-jars", {})

    def upload_texture(self, kind: str, uuid: str, access_token: str, content: bytes) -> dict:
        """kind — "skin" или "cape" (POST /api/v1/players/me/{kind})."""
        try:
            resp = self._session.post(
                f"{self.base_url}/api/v1/players/me/{kind}",
                data={"uuid": uuid, "access_token": access_token},
                files={"file": (f"{kind}.png", content, "image/png")},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ApiError(f"Не удалось связаться с сервером: {exc}") from exc
        if resp.status_code != 200:
            raise ApiError(self._extract_message(resp), status_code=resp.status_code)
        return resp.json()

    def delete_texture(self, kind: str, uuid: str, access_token: str) -> None:
        """kind — "skin" или "cape" (DELETE /api/v1/players/me/{kind})."""
        try:
            resp = self._session.delete(
                f"{self.base_url}/api/v1/players/me/{kind}",
                data={"uuid": uuid, "access_token": access_token},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ApiError(f"Не удалось связаться с сервером: {exc}") from exc
        if resp.status_code != 200:
            raise ApiError(self._extract_message(resp), status_code=resp.status_code)

    def get_texture_urls(self, uuid: str) -> dict[str, str]:
        """Текущие ссылки на скин/плащ игрока из Yggdrasil-профиля
        (GET /api/v1/profile) — {"skin": url, "cape": url}, без отсутствующих."""
        try:
            resp = self._session.get(
                f"{self.base_url}/api/v1/profile", params={"uuid": uuid}, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise ApiError(f"Не удалось связаться с сервером: {exc}") from exc
        if resp.status_code == 404:
            return {}
        if resp.status_code != 200:
            raise ApiError(self._extract_message(resp), status_code=resp.status_code)

        for prop in resp.json().get("properties", []):
            if prop.get("name") == "textures":
                textures = json.loads(base64.b64decode(prop["value"])).get("textures", {})
                return {kind.lower(): data["url"] for kind, data in textures.items() if "url" in data}
        return {}

    def download_bytes(self, url: str) -> bytes:
        # Бэкенд без PUBLIC_BASE_URL отдаёт относительные ссылки — достраиваем.
        url = urljoin(self.base_url + "/", url)
        try:
            resp = self._session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ApiError(f"Не удалось связаться с сервером: {exc}") from exc
        if resp.status_code != 200:
            raise ApiError(f"HTTP {resp.status_code}", status_code=resp.status_code)
        return resp.content

    def _get_dict(self, path: str) -> dict:
        try:
            resp = self._session.get(f"{self.base_url}{path}", timeout=self.timeout)
        except requests.RequestException as exc:
            raise ApiError(f"Не удалось связаться с сервером: {exc}") from exc
        if resp.status_code != 200:
            raise ApiError(self._extract_message(resp), status_code=resp.status_code)
        return resp.json()

    def _post(self, path: str, json_body: dict, expected: int) -> dict:
        try:
            resp = self._session.post(f"{self.base_url}{path}", json=json_body, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ApiError(f"Не удалось связаться с сервером: {exc}") from exc
        if resp.status_code != expected:
            raise ApiError(self._extract_message(resp), status_code=resp.status_code)
        return resp.json()

    def _get(self, path: str, params: dict) -> list[dict]:
        try:
            resp = self._session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ApiError(f"Не удалось связаться с сервером: {exc}") from exc
        if resp.status_code != 200:
            raise ApiError(self._extract_message(resp), status_code=resp.status_code)
        return resp.json()

    @staticmethod
    def _extract_message(resp: requests.Response) -> str:
        try:
            body = resp.json()
            return body.get("detail") or body.get("errorMessage") or body.get("error_message") or str(body)
        except ValueError:
            return resp.text or f"HTTP {resp.status_code}"
