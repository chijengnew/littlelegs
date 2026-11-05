"""會員對應與狀態。

- Firebase UID ↔ users.firebase_uid（唯一、精確比較）。
- 首次登入建立本地會員：先以 check_revoked=True 驗證；取得 UID 協調鎖後「再次」撤銷檢查，才插入。
  已刪除或停用的帳號驗證會失敗 → 拒絕，不建立。舊 Token 不得重建已刪除會員。
- deleting 狀態拒絕一般操作。
- Email 未驗證（ID Token 的 email_verified 不為 True）不建立、也不使用本地會員：回 EMAIL_NOT_VERIFIED，
  由依賴層決定以訪客處理（查詢類）或拒絕（會員專屬 API）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.locks import uid_lock
from app.db.models import User
from app.errors import ApiError
from app.ids import new_id
from app.security.firebase import AuthClaims
from app.state import AppState


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    uid: str
    auth_time: int | None


async def resolve_user(st: AppState, token: str) -> CurrentUser:
    claims = await st.verifier.verify_id_token(token, check_revoked=False)
    if not claims.email_verified:
        raise ApiError(403, "EMAIL_NOT_VERIFIED", "請先完成 Email 驗證才能使用會員功能")
    async with st.factory() as s:
        row = (await s.execute(select(User.id, User.status).where(User.firebase_uid == claims.uid))).first()
    if row is not None:
        if row.status != "active":
            raise ApiError(403, "ACCOUNT_DELETING", "帳號刪除處理中")
        return CurrentUser(row.id, claims.uid, claims.auth_time)
    return await _create_user(st, token, claims)


async def _create_user(st: AppState, token: str, first: AuthClaims) -> CurrentUser:
    await st.verifier.verify_id_token(token, check_revoked=True)
    async with uid_lock(st.engine, first.uid):
        claims = await st.verifier.verify_id_token(token, check_revoked=True)
        async with st.factory() as s, s.begin():
            row = (await s.execute(select(User.id, User.status).where(User.firebase_uid == claims.uid))).first()
            if row is not None:
                if row.status != "active":
                    raise ApiError(403, "ACCOUNT_DELETING", "帳號刪除處理中")
                return CurrentUser(row.id, claims.uid, claims.auth_time)
            uid_ = new_id()
            try:
                s.add(User(id=uid_, firebase_uid=claims.uid, status="active", locale="zh-TW"))
                await s.flush()
            except IntegrityError:
                raise ApiError(409, "USER_CREATE_CONFLICT", "請重試") from None
        return CurrentUser(uid_, claims.uid, claims.auth_time)


async def lock_active_user(s: AsyncSession, user_id: uuid.UUID) -> None:
    """受保護寫入：在同一短交易以共享鎖鎖住會員狀態；deleting 提交後不允許新寫入。"""
    status = (
        await s.execute(text("SELECT status FROM users WHERE id = :id FOR SHARE"), {"id": user_id.bytes})
    ).scalar()
    if status is None:
        raise ApiError(401, "AUTH_REAUTH_REQUIRED", "會員不存在")
    if status != "active":
        raise ApiError(403, "ACCOUNT_DELETING", "帳號刪除處理中")
