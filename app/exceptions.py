from typing import Any

from fastapi import status
from fastapi.exceptions import HTTPException


class NotFound(HTTPException):
    def __init__(self, detail: Any = None, status_code: int = status.HTTP_404_NOT_FOUND,
                 headers: dict[str, Any] | None = None):
        super(NotFound, self).__init__(status_code, detail, headers)


class DisallowedPath(HTTPException):
    def __init__(self, detail: Any = None, status_code: int = status.HTTP_403_FORBIDDEN,
                 headers: dict[str, Any] | None = None):
        super(DisallowedPath, self).__init__(status_code, detail, headers)


class Unauthorized(HTTPException):
    def __init__(self, detail: Any = None, status_code: int = status.HTTP_401_UNAUTHORIZED,
                 headers: dict[str, Any] | None = None):
        super(Unauthorized, self).__init__(status_code, detail, headers)


class ParsingError(HTTPException):
    def __init__(self, detail: Any = None, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
                 headers: dict[str, Any] | None = None):
        super(ParsingError, self).__init__(status_code, detail, headers)
