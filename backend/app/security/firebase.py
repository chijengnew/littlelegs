"""Firebase ID Token 與 App Check 驗證。

- 身分只取自驗證成功的 Token，不信任前端傳入的 uid。
- 撤銷檢查（check_revoked=True）會發網路請求：以受限執行緒池執行並設逾時，不阻塞事件迴圈。
- 建立本地會員與敏感操作一律 check_revoked=True；刪帳另要求 auth_time 在 5 分鐘內。
- 取消註冊與清理逾期未驗證帳號以 Admin 讀取帳號目前狀態（AccountInfo），不依 Token 內的 email_verified。
- App Check 與 Auth 分開驗證，互不取代；一般驗證不是一次性防重放。
"""

from __future__ import annotations

import functools
import json
import os
from dataclasses import dataclass
from typing import Protocol

import anyio

from app.errors import ApiError


@dataclass(frozen=True)
class AuthClaims:
    uid: str
    auth_time: int | None
    sign_in_provider: str | None
    email_verified: bool = False


@dataclass(frozen=True)
class AccountInfo:
    """Firebase Admin 讀到的帳號目前狀態（取消註冊與清理逾期未驗證帳號用，不信任 Token 內可能過時的值）。"""

    uid: str
    email_verified: bool
    providers: tuple[str, ...]
    created_at_ms: int | None


def account_info(record: object) -> AccountInfo:
    """firebase-admin 的 UserRecord／ExportedUserRecord → AccountInfo。"""
    meta = getattr(record, "user_metadata", None)
    return AccountInfo(
        record.uid,  # type: ignore[attr-defined]
        getattr(record, "email_verified", False) is True,
        tuple(p.provider_id for p in getattr(record, "provider_data", None) or []),
        getattr(meta, "creation_timestamp", None),
    )


def claims_from_decoded(decoded: dict) -> AuthClaims:
    """firebase-admin 解出的 ID Token 內容 → AuthClaims（只信任已驗證簽章的 Token）。"""
    fb = decoded.get("firebase") or {}
    return AuthClaims(
        decoded["uid"], decoded.get("auth_time"), fb.get("sign_in_provider"), decoded.get("email_verified") is True
    )


class Verifier(Protocol):
    async def verify_id_token(self, token: str, check_revoked: bool) -> AuthClaims: ...

    async def verify_app_check(self, token: str) -> None: ...

    async def delete_user(self, uid: str) -> None: ...

    async def get_account(self, uid: str) -> AccountInfo | None: ...

    async def list_unverified_accounts(self) -> list[AccountInfo]: ...


_limiter: anyio.CapacityLimiter | None = None


def _thread_limiter() -> anyio.CapacityLimiter:
    global _limiter
    if _limiter is None:
        _limiter = anyio.CapacityLimiter(8)
    return _limiter


async def _run_sync(fn, *args, timeout: float = 10.0):
    with anyio.fail_after(timeout):
        return await anyio.to_thread.run_sync(
            functools.partial(fn, *args), limiter=_thread_limiter(), abandon_on_cancel=True
        )


class FirebaseVerifier:
    """firebase-admin 實作。憑證由 lifespan 從 Parameter Store／環境載入；SDK 網路 timeout 另設。"""

    def __init__(self, project_id: str | None) -> None:
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            cred_json = os.environ.get("FIREBASE_ADMIN_CREDENTIALS_JSON")
            cred = credentials.Certificate(json.loads(cred_json)) if cred_json else credentials.ApplicationDefault()
            opts: dict[str, object] = {"httpTimeout": 10}
            if project_id:
                opts["projectId"] = project_id
            firebase_admin.initialize_app(cred, options=opts)

    async def verify_id_token(self, token: str, check_revoked: bool) -> AuthClaims:
        from firebase_admin import auth

        try:
            claims = await _run_sync(auth.verify_id_token, token, None, check_revoked)
        except auth.ExpiredIdTokenError as e:
            raise ApiError(401, "AUTH_TOKEN_EXPIRED", "登入憑證已過期") from e
        except (auth.RevokedIdTokenError, auth.UserDisabledError) as e:
            raise ApiError(401, "AUTH_REAUTH_REQUIRED", "需要重新登入") from e
        except auth.UserNotFoundError as e:
            raise ApiError(401, "AUTH_REAUTH_REQUIRED", "帳號不存在") from e
        except auth.CertificateFetchError as e:
            raise ApiError(503, "AUTH_UNAVAILABLE", "暫時無法驗證登入") from e
        except (auth.InvalidIdTokenError, ValueError) as e:
            raise ApiError(401, "AUTH_TOKEN_INVALID", "登入憑證無效") from e
        except TimeoutError as e:
            raise ApiError(503, "AUTH_UNAVAILABLE", "驗證逾時") from e
        return claims_from_decoded(claims)

    async def verify_app_check(self, token: str) -> None:
        from firebase_admin import app_check

        try:
            await _run_sync(app_check.verify_token, token)
        except TimeoutError as e:
            raise ApiError(503, "APP_CHECK_UNAVAILABLE", "暫時無法驗證 App Check") from e
        except Exception as e:
            raise ApiError(403, "APP_CHECK_FAILED", "App Check 驗證失敗") from e

    async def delete_user(self, uid: str) -> None:
        from firebase_admin import auth

        try:
            await _run_sync(auth.delete_user, uid)
        except auth.UserNotFoundError:
            return

    async def get_account(self, uid: str) -> AccountInfo | None:
        from firebase_admin import auth

        try:
            return account_info(await _run_sync(auth.get_user, uid))
        except auth.UserNotFoundError:
            return None

    async def list_unverified_accounts(self) -> list[AccountInfo]:
        from firebase_admin import auth

        def collect() -> list[AccountInfo]:
            return [account_info(u) for u in auth.list_users().iterate_all() if u.email_verified is not True]

        return await _run_sync(collect, timeout=300.0)
