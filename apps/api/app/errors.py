"""One error response shape for the whole API.

Every non-2xx response body looks like this, whatever raised it:

    {"error": {"code": "not_found", "message": "Event not found.", "details": null}}

`code` is a stable snake_case identifier that clients may branch on. `message` is for
humans and may change. `details` is a list of field errors for validation failures, and
null otherwise.
"""

import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class FieldError(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[FieldError] | None = None


class ErrorResponse(BaseModel):
    """Documented in OpenAPI so generated clients know the error shape."""

    error: ErrorBody


class AppError(Exception):
    """Raise from services and dependencies; the handler renders the standard shape."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[FieldError] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


# Fallback codes for errors raised by the framework rather than by our code.
_STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "too_many_requests",
    503: "service_unavailable",
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[FieldError] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers=headers,
    )


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(exc.status_code, exc.code, exc.message, exc.details, exc.headers)


async def _http_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _STATUS_CODES.get(exc.status_code, "http_error")
    if isinstance(exc.detail, str) and exc.detail:
        message = exc.detail
    else:
        message = HTTPStatus(exc.status_code).phrase
    return error_response(exc.status_code, code, message, headers=exc.headers)


def _field_errors(raw: Any) -> list[FieldError]:
    # Pydantic's `ctx` can hold arbitrary objects (e.g. the ValueError a validator raised),
    # which are not JSON-serialisable. Keep only the three stable keys.
    return [
        FieldError(loc=list(e.get("loc", ())), msg=str(e.get("msg", "")), type=str(e["type"]))
        for e in raw
    ]


async def _validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return error_response(
        422, "validation_error", "The request is invalid.", _field_errors(exc.errors())
    )


async def _unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    return error_response(500, "internal_error", "Something went wrong on our side.")


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
