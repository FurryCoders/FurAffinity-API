from fastapi.exceptions import HTTPException


class NotFound(HTTPException):
    pass


class DisallowedPath(HTTPException):
    pass


class Unauthorized(HTTPException):
    pass
