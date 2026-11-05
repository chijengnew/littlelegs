"""FastAPI 依賴：狀態、來源 IP、App Check、身分、限流。

- 來源 IP 取自 uvicorn 以 --forwarded-allow-ips=127.0.0.1 處理後的 request.client.host；
  不直接讀取使用者可偽造的 X-Forwarded-For。
- 所有使用者可觸發付費外部 API 的端點驗 App Check；OPTIONS 預檢由 CORS middleware 處理，不經這些依賴。
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, Request

from app.errors import ApiError
from app.ratelimit import QuotaExceeded, quota_api_error
from app.services.users import CurrentUser, resolve_user
from app.state import AppState


def get_state(request: Request) -> AppState:
    return request.app.state.ll


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def app_check(
    request: Request, x_firebase_appcheck: str | None = Header(default=None), st: AppState = Depends(get_state)
) -> None:
    if not st.settings.app_check_enforce:
        return
    if not x_firebase_appcheck:
        raise ApiError(403, "APP_CHECK_REQUIRED", "缺少 App Check Token")
    await st.verifier.verify_app_check(x_firebase_appcheck)


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, tok = authorization.partition(" ")
    if scheme.lower() != "bearer" or not tok.strip():
        raise ApiError(401, "AUTH_TOKEN_INVALID", "Authorization 格式錯誤")
    return tok.strip()


async def optional_user(
    request: Request, authorization: str | None = Header(default=None), st: AppState = Depends(get_state)
) -> CurrentUser | None:
    tok = _bearer(authorization)
    if tok is None:
        return None
    try:
        return await resolve_user(st, tok)
    except ApiError as e:
        if e.code != "EMAIL_NOT_VERIFIED":
            raise
        request.state.email_not_verified = True
        return None


async def require_user(request: Request, user: CurrentUser | None = Depends(optional_user)) -> CurrentUser:
    if user is None:
        if getattr(request.state, "email_not_verified", False):
            raise ApiError(403, "EMAIL_NOT_VERIFIED", "請先完成 Email 驗證才能使用會員功能")
        raise ApiError(401, "AUTH_REQUIRED", "此功能需要登入")
    return user


def _raise_quota(e: QuotaExceeded) -> None:
    raise ApiError(
        429, "RATE_LIMITED", "請求過於頻繁，請稍後再試", headers={"Retry-After": "60"}, extra={"limit_window": e.window}
    )


def limit(category: str) -> Callable:
    """category: paid / endpoint_select / general"""

    async def dep(
        request: Request, user: CurrentUser | None = Depends(optional_user), st: AppState = Depends(get_state)
    ) -> None:
        try:
            await st.limiter.inbound(category, client_ip(request), user.uid if user else None)
        except QuotaExceeded as e:
            _raise_quota(e)

    return dep


async def feedback_limit(request: Request, st: AppState = Depends(get_state)) -> None:
    """回饋不看登入身分：同時套用全站與回饋專用的每 IP 上限。"""
    try:
        await st.limiter.inbound("feedback", client_ip(request), None)
    except QuotaExceeded as e:
        _raise_quota(e)


def quota_error(e: QuotaExceeded) -> ApiError:
    return quota_api_error(e)
