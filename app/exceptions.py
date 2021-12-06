from typing import Any

from fastapi import status
from fastapi.exceptions import HTTPException


class NotFound(HTTPException):
    def __init__(self, status_code: int = status.HTTP_404_NOT_FOUND, detail: Any = None,
                 headers: dict[str, Any] = None):
        super(NotFound, self).__init__(status_code, detail, headers)


class DisallowedPath(HTTPException):
    def __init__(self, status_code: int = status.HTTP_401_UNAUTHORIZED, detail: Any = None,
                 headers: dict[str, Any] = None):
        super(DisallowedPath, self).__init__(status_code, detail, headers)


class Unauthorized(HTTPException):
    def __init__(self, status_code: int = status.HTTP_403_FORBIDDEN, detail: Any = None,
                 headers: dict[str, Any] = None):
        super(Unauthorized, self).__init__(status_code, detail, headers)
