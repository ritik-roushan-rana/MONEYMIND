# backend/errors.py

from __future__ import annotations

from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
JOB_NOT_DONE = "JOB_NOT_DONE"
JOB_FAILED = "JOB_FAILED"
INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
BANK_NOT_DETECTED = "BANK_NOT_DETECTED"
PIPELINE_ERROR = "PIPELINE_ERROR"


class APIError(Exception):
    """Raised from route handlers; rendered by `api_error_handler` into the
    consistent `{"detail": ..., "error_code": ..., ...extra}` body."""

    def __init__(self, status_code: int, error_code: str, detail: str,
                 extra: Optional[dict[str, Any]] = None):
        super().__init__(detail)
        self.status_code = status_code
        self.error_code = error_code
        self.detail = detail
        self.extra = extra or {}


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    body = {"detail": exc.detail, "error_code": exc.error_code}
    body.update(exc.extra)
    return JSONResponse(status_code=exc.status_code, content=body)
