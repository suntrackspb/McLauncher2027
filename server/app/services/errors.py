class ServiceError(Exception):
    """Ошибка бизнес-логики. Роут сам решает, в каком формате её вернуть
    (обычный JSON для наших /auth эндпоинтов, Yggdrasil-формат для /session)."""

    def __init__(self, message: str, *, error_code: str = "ERROR"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
