"""未完成的註冊：Email／密碼註冊後尚未點驗證連結的帳號（2026-11-02 決定：註冊須完成驗證，否則不保留帳號）。

- Firebase 要先建立帳號才能寄驗證信；驗證前不建立本地會員（見 users.py），限流也只以 IP 計（見 deps.limit）。
  取消時只刪 Firebase 帳號，不建立或刪除會員業務資料；IP 限流仍可能寫入計數，並須讀取會員、取得 UID 協調鎖。
- 使用者在驗證頁按「取消註冊」立即刪除；已滿 PENDING_TTL 仍未驗證者由定時工作刪除（deletion_worker purge-unverified）。
- 只刪「Email 未驗證、只有 Email／密碼登入方式、沒有本地會員」的帳號，並以 Firebase Admin 讀取的目前狀態為準，
  不信任 ID Token 內可能過時的 email_verified。
- 與建立會員共用 UID 協調鎖，鎖內再確認一次，不會刪到剛完成驗證、正在建立會員的帳號。
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select

from app.db.locks import uid_lock
from app.db.models import User
from app.errors import ApiError
from app.security.firebase import AccountInfo
from app.state import AppState

log = logging.getLogger("littlelegs.registration")

PENDING_TTL = timedelta(hours=24)


def is_pending(info: AccountInfo) -> bool:
    """未完成註冊：Email 未驗證，且只有 Email／密碼登入方式（Google 等由提供者證明信箱，不算）。"""
    return not info.email_verified and bool(info.providers) and set(info.providers) <= {"password"}


def is_expired(info: AccountInfo, now: datetime) -> bool:
    """未完成註冊且建立已滿 PENDING_TTL；建立時間不明者不刪。"""
    cutoff_ms = int((now - PENDING_TTL).timestamp() * 1000)
    return is_pending(info) and info.created_at_ms is not None and info.created_at_ms <= cutoff_ms


async def _has_member(st: AppState, uid: str) -> bool:
    async with st.factory() as s:
        return (await s.execute(select(User.id).where(User.firebase_uid == uid))).first() is not None


async def _delete_if_pending(st: AppState, uid: str) -> bool:
    """鎖內確認仍是未完成註冊才刪除；帳號已不存在視為已刪除。已驗證或已有會員回 False（不刪）。"""
    async with uid_lock(st.engine, uid):
        if await _has_member(st, uid):
            return False
        info = await st.verifier.get_account(uid)
        if info is None:
            return True
        if not is_pending(info):
            return False
        await st.verifier.delete_user(uid)
    return True


async def cancel_registration(st: AppState, token: str) -> None:
    """使用者取消註冊；不要求最近登入（帳號沒有任何會員資料），仍做撤銷檢查。"""
    claims = await st.verifier.verify_id_token(token, check_revoked=True)
    if not await _delete_if_pending(st, claims.uid):
        raise ApiError(409, "REGISTRATION_COMPLETED", "Email 已完成驗證，註冊已完成，無法取消註冊")


@dataclass
class PurgeResult:
    removed: int
    failures: int


async def purge_expired(st: AppState, now: datetime) -> PurgeResult:
    """定時工作：刪除建立已滿 PENDING_TTL 仍未驗證的帳號；單筆失敗不影響其他筆，下一輪再試。"""
    out = PurgeResult(0, 0)
    for info in await st.verifier.list_unverified_accounts():
        if not is_expired(info, now):
            continue
        try:
            if await _delete_if_pending(st, info.uid):
                out.removed += 1
        except Exception:
            out.failures += 1
            uid_sha = hashlib.sha256(info.uid.encode()).hexdigest()[:12]
            log.exception("刪除逾期未驗證帳號失敗，下一輪重試 uid_sha=%s", uid_sha)
    return out
