"""RFC 9457 application/problem+json。

業務結果（infeasible／unverified）以 200 回傳，不轉成 HTTP 錯誤。
錯誤回應不得包含 Token、金鑰、孩子資料或精確位置。
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM = "application/problem+json"

TITLES = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    413: "Payload Too Large",
    422: "Unprocessable Content",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        detail: str | None = None,
        errors: list[dict] | None = None,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.status, self.code, self.detail = status, code, detail
        self.errors = errors or []
        self.headers = headers or {}
        self.extra = extra or {}


def trace_id(request: Request) -> str:
    tid = getattr(request.state, "trace_id", None)
    if tid is None:
        tid = str(uuid.uuid4())
        request.state.trace_id = tid
    return tid


def problem(
    request: Request,
    status: int,
    code: str,
    detail: str | None = None,
    errors: list[dict] | None = None,
    headers: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"https://littlelegsgo.com/problems/{code.lower().replace('_', '-')}",
        "title": TITLES.get(status, "Error"),
        "status": status,
        "code": code,
        "trace_id": trace_id(request),
    }
    if detail:
        body["detail"] = detail
    if errors:
        body["errors"] = errors
    if extra:
        body.update(extra)
    return JSONResponse(body, status_code=status, media_type=PROBLEM, headers=headers)


def _safe_validation_errors(exc: RequestValidationError) -> list[dict]:
    out = []
    for e in exc.errors():
        out.append({"loc": [str(x) for x in e.get("loc", [])], "msg": e.get("msg"), "type": e.get("type")})
    return out


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(request: Request, exc: ApiError):
        return problem(request, exc.status, exc.code, exc.detail, exc.errors, exc.headers, exc.extra)

    @app.exception_handler(RequestValidationError)
    async def _val(request: Request, exc: RequestValidationError):
        return problem(request, 422, "VALIDATION_FAILED", "輸入欄位不合法", _safe_validation_errors(exc))

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
        return problem(request, exc.status_code, code, None, None, getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        return problem(request, 500, "INTERNAL_ERROR", "伺服器發生錯誤")
