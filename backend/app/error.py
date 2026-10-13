import uuid as _uuid
from typing import List, Optional

import asyncpg
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.logger import get_logger

logger = get_logger(__name__)


class AppException(Exception):
    def __init__(
        self,
        status_code: int = 500,
        detail: str = "Internal server error",
        error_code: Optional[str] = None,
        headers: Optional[dict] = None,
    ):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        self.headers = headers
        super().__init__(detail)


class BadRequestException(AppException):
    def __init__(self, detail: str = "Bad request", error_code: str = "BAD_REQUEST"):
        super().__init__(status_code=400, detail=detail, error_code=error_code)


class UnauthorizedException(AppException):
    def __init__(self, detail: str = "Unauthorized", error_code: str = "UNAUTHORIZED"):
        super().__init__(status_code=401, detail=detail, error_code=error_code)


class NotFoundException(AppException):
    def __init__(
        self, detail: str = "Resource not found", error_code: str = "NOT_FOUND"
    ):
        super().__init__(status_code=404, detail=detail, error_code=error_code)


class ConflictException(AppException):
    def __init__(
        self, detail: str = "Resource already exists", error_code: str = "CONFLICT"
    ):
        super().__init__(status_code=409, detail=detail, error_code=error_code)


class ExternalServiceException(AppException):
    def __init__(
        self,
        detail: str = "External service error",
        error_code: str = "EXTERNAL_SERVICE_ERROR",
    ):
        super().__init__(status_code=502, detail=detail, error_code=error_code)


def validate_uuid(*values: tuple[str, str]) -> None:
    for value, param_name in values:
        try:
            _uuid.UUID(value)
        except (ValueError, AttributeError, TypeError):
            raise BadRequestException(
                f"Invalid {param_name} format. Expected a valid UUID."
            )


USER_FRIENDLY_MESSAGES = {
    "EXTERNAL_SERVICE_ERROR": "Service temporarily unavailable. Please try again later.",
    "DATABASE_ERROR": "Something went wrong. Please try again later.",
    "INTERNAL_ERROR": "Something went wrong. Please try again later.",
}

HTTP_STATUS_MESSAGES = {
    400: "BAD REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT FOUND",
    409: "CONFLICT",
    422: "UNPROCESSABLE ENTITY",
    429: "TOO MANY REQUESTS",
    500: "INTERNAL SERVER ERROR",
    502: "BAD GATEWAY",
    503: "SERVICE UNAVAILABLE",
}


def get_user_friendly_message(error: Exception) -> str:
    if isinstance(error, AppException):
        return USER_FRIENDLY_MESSAGES.get(error.error_code or "", error.detail)
    return USER_FRIENDLY_MESSAGES["INTERNAL_ERROR"]


def create_error_response(
    status_code: int,
    detail: str,
    error_code: Optional[str] = None,
    errors: Optional[List[dict]] = None,
) -> dict:
    body = {
        "status_code": status_code,
        "status_message": HTTP_STATUS_MESSAGES.get(status_code, "ERROR"),
        "message": detail,
    }
    if error_code:
        body["code"] = error_code
    if errors:
        body["details"] = errors
    return {"success": False, "error": body}


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    log = logger.error if exc.status_code >= 500 else logger.warning
    log(f"AppException: {exc.detail} | Path: {request.url.path}")
    message = USER_FRIENDLY_MESSAGES.get(exc.error_code or "", exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(exc.status_code, message, exc.error_code),
        headers=exc.headers,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    log = logger.error if exc.status_code >= 500 else logger.warning
    log(f"HTTPException: {exc.detail} | Path: {request.url.path}")
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(exc.status_code, str(exc.detail)),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {
            "field": ".".join(str(loc) for loc in e["loc"]),
            "message": e["msg"],
            "type": e["type"],
        }
        for e in exc.errors()
    ]
    logger.warning(f"Validation error | Path: {request.url.path}")
    return JSONResponse(
        status_code=422,
        content=create_error_response(
            422, "Please check your input and try again.", "VALIDATION_ERROR", errors
        ),
    )


async def asyncpg_exception_handler(
    request: Request, exc: asyncpg.PostgresError
) -> JSONResponse:
    logger.error(f"Database error | Path: {request.url.path} | Error: {exc}")
    if isinstance(exc, asyncpg.UniqueViolationError):
        return JSONResponse(
            status_code=409,
            content=create_error_response(
                409, "This resource already exists.", "CONFLICT"
            ),
        )
    return JSONResponse(
        status_code=500,
        content=create_error_response(
            500, USER_FRIENDLY_MESSAGES["DATABASE_ERROR"], "DATABASE_ERROR"
        ),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        f"Unhandled exception | Path: {request.url.path} | Error: {exc}", exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content=create_error_response(
            500, USER_FRIENDLY_MESSAGES["INTERNAL_ERROR"], "INTERNAL_ERROR"
        ),
    )


def setup_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(asyncpg.PostgresError, asyncpg_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
