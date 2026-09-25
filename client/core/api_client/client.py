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
            return body.get("detail") or body.get("error_message") or str(body)
        except ValueError:
            return resp.text or f"HTTP {resp.status_code}"
