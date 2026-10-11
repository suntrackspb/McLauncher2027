import json
from pathlib import Path

SESSION_FILENAME = "session.json"
_REQUIRED_KEYS = ("username", "uuid", "access_token")


class SessionStore:
    """Сессия игрока (username/uuid/access_token) между запусками лаунчера,
    чтобы не логиниться заново каждый раз. Токен на бэкенде перевыпускается
    только при новом логине, поэтому сохранённый остаётся рабочим, пока игрок
    не войдёт где-то ещё — тогда join на сервере не пройдёт и нужен перелогин."""

    def __init__(self, app_data_dir: Path):
        self._path = Path(app_data_dir) / SESSION_FILENAME

    def load(self) -> dict | None:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict) or not all(isinstance(data.get(k), str) for k in _REQUIRED_KEYS):
            return None
        return {k: data[k] for k in _REQUIRED_KEYS}

    def save(self, session: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(session), encoding="utf-8")

    def clear(self) -> None:
        self._path.unlink(missing_ok=True)
