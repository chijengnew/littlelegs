"""刪除流程：外部持久意圖 → 本地處理 → 完成標記；可重複執行（冪等），由定時工作補完。

- 意圖寫入明確失敗：回錯誤、未接受。結果不明：沿用同一 operation_id 查核／重試，不告知可安全取消。
- 意圖寫入成功即接受且必須完成：立即嘗試處理；失敗交由 systemd timer 每分鐘的工作依外部意圖恢復。
- 刪帳：auth_time ≤ 5 分鐘＋check_revoked；順序：意圖 → 本地 deleting → 刪 Firebase（已不存在視為成功）
  → 刪 MySQL 會員與所有關聯資料（含 UID 限流列）→ 完成標記。不保留 MySQL 會員 tombstone。
  Email 未驗證（沒有本地會員）的帳號不走這裡，改由 registration.cancel_registration「取消註冊」。
- 單筆刪除（歷史／收藏）：保留窗口內最小防重送狀態；清除不再被本人其他紀錄引用的私人端點。
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import rowcount
from app.db.locks import uid_lock
from app.db.models import (
    Favorite,
    FavoriteOperation,
    History,
    PrivateEndpoint,
    PrivateEndpointAlias,
    User,
)
from app.errors import ApiError
from app.ratelimit import delete_uid_counters
from app.services.history import delete_history_rows
from app.services.intents import DeletionIntent, IntentWriteFailed, IntentWriteUnknown
from app.state import AppState

log = logging.getLogger("littlelegs.deletion")

REAUTH_WINDOW_S = 5 * 60


@dataclass
class DeletionOutcome:
    operation_id: str
    completed: bool


def _endpoint_refs(conditions: dict | None) -> set[str]:
    out: set[str] = set()
    for k in ("start", "end"):
        ep = (conditions or {}).get(k)
        if isinstance(ep, dict) and ep.get("type") == "google_place" and ep.get("endpoint_id"):
            out.add(ep["endpoint_id"])
    return out


async def cleanup_orphan_endpoints(s: AsyncSession, user_id: uuid.UUID, candidates: set[str]) -> int:
    """刪除不再被本人任何歷史／收藏引用的私人端點（含 alias）。共用公開地點資料不受影響。"""
    if not candidates:
        return 0
    still: set[str] = set()
    for model in (History, Favorite):
        for cond in (await s.execute(select(model.conditions).where(model.user_id == user_id))).scalars():
            still |= _endpoint_refs(cond)
    orphans = [uuid.UUID(e) for e in candidates - still]
    if not orphans:
        return 0
    await s.execute(
        delete(PrivateEndpointAlias).where(
            PrivateEndpointAlias.user_id == user_id, PrivateEndpointAlias.endpoint_id.in_(orphans)
        )
    )
    r = await s.execute(
        delete(PrivateEndpoint).where(PrivateEndpoint.user_id == user_id, PrivateEndpoint.id.in_(orphans))
    )
    return rowcount(r)


async def _accept(st: AppState, intent: DeletionIntent) -> None:
    try:
        await st.intents.put_intent(intent)
    except IntentWriteFailed as e:
        raise ApiError(503, "DELETION_NOT_ACCEPTED", "刪除請求未被接受，請稍後再試") from e
    except IntentWriteUnknown as e:
        raise ApiError(
            503,
            "DELETION_RESULT_UNKNOWN",
            "無法確認刪除請求是否已接受，請以相同操作識別碼重試",
            extra={"operation_id": intent.operation_id},
        ) from e


def _now_iso(st: AppState) -> str:
    return st.clock().astimezone(UTC).isoformat()


async def process_intent(st: AppState, intent: DeletionIntent) -> bool:
    """冪等處理一筆意圖；全部必要步驟完成才寫完成標記並回 True。"""
    uid = uuid.UUID(intent.user_id)
    if intent.kind == "account":
        await _process_account(st, uid, intent.firebase_uid)
    elif intent.kind == "history":
        async with st.factory() as s, s.begin():
            h = (
                await s.execute(
                    select(History.conditions).where(History.id == uuid.UUID(intent.target_id), History.user_id == uid)
                )
            ).scalar()
            if await delete_history_rows(s, uid, uuid.UUID(intent.target_id)):
                await cleanup_orphan_endpoints(s, uid, _endpoint_refs(h))
    elif intent.kind == "favorite":
        async with st.factory() as s, s.begin():
            await _delete_favorite_rows(s, uid, uuid.UUID(intent.target_id))
    else:
        raise ValueError(f"未知意圖類型 {intent.kind}")
    await st.intents.mark_completed(intent.operation_id, _now_iso(st))
    return True


async def _delete_favorite_rows(s: AsyncSession, user_id: uuid.UUID, fid: uuid.UUID) -> None:
    await s.execute(
        update(FavoriteOperation)
        .where(
            FavoriteOperation.user_id == user_id,
            FavoriteOperation.favorite_id == fid,
            FavoriteOperation.op_type == "create",
        )
        .values(state="cancelled")
    )
    cond = (
        await s.execute(select(Favorite.conditions).where(Favorite.id == fid, Favorite.user_id == user_id))
    ).scalar()
    r = await s.execute(delete(Favorite).where(Favorite.id == fid, Favorite.user_id == user_id))
    if rowcount(r):
        await cleanup_orphan_endpoints(s, user_id, _endpoint_refs(cond))


async def _process_account(st: AppState, user_id: uuid.UUID, firebase_uid: str | None) -> None:
    async with st.factory() as s, s.begin():
        await s.execute(update(User).where(User.id == user_id).values(status="deleting"))
    if firebase_uid:
        async with uid_lock(st.engine, firebase_uid):
            await st.verifier.delete_user(firebase_uid)
            async with st.factory() as s, s.begin():
                await delete_uid_counters(s, firebase_uid)
                await s.execute(delete(User).where(User.id == user_id))
    else:
        async with st.factory() as s, s.begin():
            await s.execute(delete(User).where(User.id == user_id))


async def request_record_deletion(
    st: AppState, user_id: uuid.UUID, kind: str, target: uuid.UUID, operation_id: uuid.UUID
) -> DeletionOutcome:
    """歷史／收藏單筆刪除。先驗擁有權；不存在時若同 operation_id 已完成則回完成，否則 404。"""
    op = str(operation_id)
    existing = await st.intents.get_intent(op)
    if existing is not None:
        if (existing.kind, existing.user_id, existing.target_id) != (kind, str(user_id), str(target)):
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "同一操作識別碼已用於其他刪除")
    else:
        model = History if kind == "history" else Favorite
        async with st.factory() as s:
            owned = (await s.execute(select(model.id).where(model.id == target, model.user_id == user_id))).scalar()
        if owned is None:
            raise ApiError(404, f"{kind.upper()}_NOT_FOUND", "找不到此紀錄")
        existing = DeletionIntent(op, kind, str(user_id), None, str(target), _now_iso(st))
        await _accept(st, existing)
    if await st.intents.is_completed(op):
        return DeletionOutcome(op, True)
    try:
        return DeletionOutcome(op, await process_intent(st, existing))
    except Exception:
        log.exception("刪除處理失敗，交由定時工作重試", extra={"operation_id": op, "kind": kind})
        return DeletionOutcome(op, False)


async def request_account_deletion(st: AppState, token: str, operation_id: uuid.UUID) -> DeletionOutcome:
    """不經一般會員依賴：deleting 狀態的會員仍須能以同一 operation_id 重試／查核。"""
    claims = await st.verifier.verify_id_token(token, check_revoked=True)
    now_s = int(st.clock().timestamp())
    if claims.auth_time is None or now_s - int(claims.auth_time) > REAUTH_WINDOW_S:
        raise ApiError(401, "REAUTH_REQUIRED", "請重新登入後 5 分鐘內再刪除帳號")
    async with st.factory() as s:
        user_id = (await s.execute(select(User.id).where(User.firebase_uid == claims.uid))).scalar()
    op = str(operation_id)
    existing = await st.intents.get_intent(op)
    if user_id is None:
        if existing is not None and existing.firebase_uid == claims.uid:
            user_id = uuid.UUID(existing.user_id)
        else:
            raise ApiError(404, "USER_NOT_FOUND", "找不到會員資料")
    if existing is not None and (existing.kind, existing.user_id) != ("account", str(user_id)):
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "同一操作識別碼已用於其他刪除")
    if existing is None:
        existing = DeletionIntent(op, "account", str(user_id), claims.uid, None, _now_iso(st))
        await _accept(st, existing)
    try:
        async with st.factory() as s, s.begin():
            await s.execute(update(User).where(User.id == user_id).values(status="deleting"))
    except Exception:
        log.exception("本地 deleting 標記失敗；由外部意圖恢復", extra={"operation_id": op})
        return DeletionOutcome(op, False)
    try:
        return DeletionOutcome(op, await process_intent(st, existing))
    except Exception:
        log.exception("刪帳處理失敗，交由定時工作重試", extra={"operation_id": op})
        return DeletionOutcome(op, False)


async def deletion_status(st: AppState, user_id: uuid.UUID, operation_id: uuid.UUID) -> dict:
    op = str(operation_id)
    intent = await st.intents.get_intent(op)
    if intent is None or intent.user_id != str(user_id):
        raise ApiError(404, "DELETION_NOT_FOUND", "找不到此刪除請求")
    done = await st.intents.is_completed(op)
    return {
        "operation_id": op,
        "kind": intent.kind,
        "status": "completed" if done else "accepted",
        "accepted_at": intent.accepted_at,
    }


def now_utc() -> datetime:
    return datetime.now(UTC)
