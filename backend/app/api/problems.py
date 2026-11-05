"""錯誤回應的 OpenAPI 說明：與實際回傳的 application/problem+json 格式一致。

實際回應由 app.errors 產生；這裡只負責讓 /docs 與 openapi.json 描述同一個格式，
並為每個狀態碼附上該端點實際可能出現的範例。
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from app.errors import PROBLEM, TITLES


class FieldError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    loc: list[str] = Field(description='欄位位置，例如 ["body", "conditions", "depart_time"]')
    msg: str | None = Field(default=None, description="原因")
    type: str | None = Field(default=None, description="驗證錯誤類型")


class Problem(BaseModel):
    """統一錯誤格式（RFC 9457）。依 `code` 判斷錯誤種類，`detail` 是給使用者看的說明；
    後四個欄位只在特定錯誤出現。"""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(description="錯誤類型的識別網址")
    title: str = Field(description="HTTP 狀態的標準名稱")
    status: int = Field(description="HTTP 狀態碼")
    code: str = Field(description="錯誤代碼，例如 DEPARTURE_PASSED、VALIDATION_FAILED、RATE_LIMITED")
    trace_id: str = Field(description="追蹤識別碼，與回應標頭 X-Trace-Id 相同")
    detail: str | None = Field(default=None, description="繁體中文說明")
    errors: list[FieldError] | None = Field(default=None, description="欄位錯誤（輸入驗證失敗時）")
    limit_window: str | None = Field(default=None, description="限流或額度的計算窗口（429）")
    current_revision: int | None = Field(default=None, description="目前的行程版本（版本衝突時）")
    history_id: str | None = Field(default=None, description="進行中的歷史 ID（搜尋進行中時）")
    operation_id: str | None = Field(default=None, description="刪除操作 ID（刪除結果未知時）")


_DESCRIPTIONS = {
    401: "登入憑證無效、過期或需要重新登入",
    403: "拒絕存取：App Check 驗證失敗、Email 尚未驗證（會員功能）、帳號刪除中，或無權使用此起訖點",
    404: "找不到指定的資料",
    409: "與目前狀態衝突：例如出發時間已過、同一識別碼的內容不同、行程已在別處更新",
    422: "輸入欄位不合法；`errors` 列出欄位位置與原因",
    429: "請求過於頻繁，或外部服務額度已用完；`limit_window` 標示計算窗口",
    500: "伺服器發生錯誤",
    503: "外部服務或驗證服務暫時無法使用",
}

_EXAMPLE_TRACE_ID = "ad9a4ff0-8104-42c9-8763-e6ddb4296f3e"


def _example(status: int, code: str, detail: str, **extra: Any) -> dict[str, Any]:
    """與 app.errors.problem() 產生的回應同一結構。"""
    return {
        "type": f"https://littlelegsgo.com/problems/{code.lower().replace('_', '-')}",
        "title": TITLES[status],
        "status": status,
        "code": code,
        "trace_id": _EXAMPLE_TRACE_ID,
        "detail": detail,
        **extra,
    }


def _response(status: int, code: str, detail: str, **extra: Any) -> dict[int | str, dict[str, Any]]:
    return {
        status: {
            "model": Problem,
            "description": _DESCRIPTIONS[status],
            "content": {"application/json": {"example": _example(status, code, detail, **extra)}},
        }
    }


def not_found(code: str, detail: str) -> dict[int | str, dict[str, Any]]:
    return _response(404, code, detail)


def forbidden(code: str, detail: str) -> dict[int | str, dict[str, Any]]:
    return _response(403, code, detail)


EMAIL_NOT_VERIFIED = forbidden("EMAIL_NOT_VERIFIED", "請先完成 Email 驗證才能使用會員功能")


def conflict(code: str, detail: str) -> dict[int | str, dict[str, Any]]:
    return _response(409, code, detail)


def common_errors(
    *, app_check: bool, conflict_example: tuple[str, str], member_only: bool = False
) -> dict[int | str, dict[str, Any]]:
    """每個 /v1 端點都可能發生的錯誤：帶了無效的登入憑證、帳號狀態、限流、輸入驗證、伺服器或驗證服務錯誤。

    409 至少可能來自首次登入建立會員時的併發衝突；範例取該組端點最常見的一種。
    會員專屬端點的 403 範例為 Email 尚未驗證（查詢類端點對未驗證帳號改以訪客處理，不回此錯誤）。
    """
    out: dict[int | str, dict[str, Any]] = {}
    out |= _response(401, "AUTH_TOKEN_EXPIRED", "登入憑證已過期")
    if app_check:
        out |= _response(403, "APP_CHECK_REQUIRED", "缺少 App Check Token")
    elif member_only:
        out |= EMAIL_NOT_VERIFIED
    else:
        out |= _response(403, "ACCOUNT_DELETING", "帳號刪除處理中")
    out |= conflict(*conflict_example)
    out |= _response(
        422,
        "VALIDATION_FAILED",
        "輸入欄位不合法",
        errors=[
            {
                "loc": ["body", "conditions", "depart_time"],
                "msg": "Value error, 時間必須是 15 分鐘刻度",
                "type": "value_error",
            }
        ],
    )
    out |= _response(429, "RATE_LIMITED", "請求過於頻繁，請稍後再試", limit_window="minute")
    out |= _response(500, "INTERNAL_ERROR", "伺服器發生錯誤")
    out |= (
        _response(503, "APP_CHECK_UNAVAILABLE", "暫時無法驗證 App Check")
        if app_check
        else _response(503, "AUTH_UNAVAILABLE", "暫時無法驗證登入")
    )
    return out


DELETE_CONFLICT = conflict("IDEMPOTENCY_CONFLICT", "同一操作識別碼已用於其他刪除")


def use_problem_media_type(app: FastAPI) -> None:
    """FastAPI 預設把錯誤回應的格式標成 application/json；改成實際使用的 application/problem+json。"""
    base = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = base()
            for item in schema.get("paths", {}).values():
                for op in item.values():
                    for status, resp in op.get("responses", {}).items():
                        content = resp.get("content", {})
                        if status[:1] in ("4", "5") and "application/json" in content:
                            content[PROBLEM] = content.pop("application/json")
        return app.openapi_schema or {}

    app.openapi = openapi  # type: ignore[method-assign]
