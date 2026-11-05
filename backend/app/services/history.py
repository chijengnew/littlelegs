"""會員歷史。

- 有效候選搜尋在「外部呼叫前」以 query_id 建立歷史（searching），完成後更新 succeeded／partial／failed。
- 同一 query_id 重試不新增；搜尋中重送回既有狀態，不平行啟動重複付費搜尋（search_run_id＋期限租約）。
  只有目前 run 可更新狀態；過期的 searching 可由新一輪接手，晚到的舊結果不能覆寫。
- query_operations 保留最小條件指紋與 created／deleted 狀態至操作窗口結束，防止刪除後延遲重送重建。
- 操作窗口 expires_at = max(key_time + 7 天, 出發時間點)，首次建立時固定；過期只允許閱讀／刪除。
- 行程更新以 revision 樂觀併發：expected_revision 不符回 409，不讓較慢回應覆寫較新順序。
"""

from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import rowcount
from app.db.models import Favorite, History, HistoryStop, QueryOperation
from app.domain.fingerprint import FINGERPRINT_VERSION, conditions_fingerprint, endpoint_identity
from app.domain.schemas import Conditions, GooglePlaceEndpoint
from app.domain.validation import check_key_time, query_window_end
from app.errors import ApiError
from app.ids import new_id
from app.services.endpoints import ensure_private_endpoint
from app.services.users import lock_active_user

SEARCH_LEASE = timedelta(seconds=45)


@dataclass
class StoredStop:
    place_id: uuid.UUID
    stay_minutes: int
    stay_source: str
    google_place_id: str | None


async def member_endpoint_ids(s: AsyncSession, user_id: uuid.UUID, c: Conditions) -> tuple[str, str, dict]:
    """把會員的 google_place 端點映射到私人端點身分（不呼叫 Google），回傳 (start_id, end_id, 儲存用 conditions)。"""
    stored = c.model_dump(mode="json")
    ids = []
    for key, ep in (("start", c.start), ("end", c.end_or_start)):
        if isinstance(ep, GooglePlaceEndpoint):
            eid = await ensure_private_endpoint(s, user_id, ep.google_place_id)
            if key in stored and stored[key] is not None:
                stored[key]["endpoint_id"] = str(eid)
                stored[key].pop("label", None)
            ids.append(endpoint_identity(ep, str(eid)))
        else:
            if key in stored and stored[key] is not None and ep.type == "device_coordinate":
                stored[key].pop("label", None)
            ids.append(endpoint_identity(ep))
    return ids[0], ids[1], stored


def _labels(c: Conditions) -> tuple[str | None, str | None]:
    sl = getattr(c.start, "label", None)
    el = getattr(c.end, "label", None) if c.end is not None else sl
    return sl, el


async def _operation(
    s: AsyncSession, user_id: uuid.UUID, qid: uuid.UUID, fp: bytes, c: Conditions, now: datetime, create: bool
) -> QueryOperation | None:
    op = (
        await s.execute(
            select(QueryOperation)
            .where(QueryOperation.user_id == user_id, QueryOperation.query_id == qid)
            .with_for_update()
        )
    ).scalar()
    if op is not None:
        if now >= op.expires_at:
            raise ApiError(409, "OPERATION_EXPIRED", "此查詢的操作期限已過，請建立新查詢")
        if op.state == "deleted":
            raise ApiError(409, "HISTORY_DELETED", "此查詢的歷史已刪除，請建立新查詢")
        if op.request_fingerprint != fp:
            raise ApiError(409, "QUERY_CONDITIONS_CONFLICT", "同一 query_id 的條件不同，請以新查詢送出")
        return op
    if not create:
        return None
    exp = query_window_end(qid, c)
    if now >= exp:
        raise ApiError(409, "OPERATION_EXPIRED", "此查詢的操作期限已過，請建立新查詢")
    op = QueryOperation(
        user_id=user_id,
        query_id=qid,
        request_fingerprint=fp,
        fingerprint_version=FINGERPRINT_VERSION,
        state="created",
        expires_at=exp,
        created_at=now,
    )
    s.add(op)
    await s.flush()
    return op


async def begin_search(
    factory, user_id: uuid.UUID, qid: uuid.UUID, c: Conditions, now: datetime
) -> tuple[uuid.UUID, uuid.UUID]:
    check_key_time(qid, now)
    for attempt in range(2):
        try:
            async with factory() as s, s.begin():
                await lock_active_user(s, user_id)
                sid, eid, stored = await member_endpoint_ids(s, user_id, c)
                fp = conditions_fingerprint(c, sid, eid)
                h = (
                    await s.execute(
                        select(History).where(History.user_id == user_id, History.query_id == qid).with_for_update()
                    )
                ).scalar()
                op = await _operation(s, user_id, qid, fp, c, now, create=h is None)
                if h is not None and op is None:
                    raise ApiError(409, "OPERATION_EXPIRED", "此查詢的操作期限已過，請建立新查詢")
                if h is not None and h.conditions_fingerprint != fp:
                    raise ApiError(409, "QUERY_CONDITIONS_CONFLICT", "同一 query_id 的條件不同，請以新查詢送出")
                run = new_id()
                if h is None:
                    sl, el = _labels(c)
                    h = History(
                        id=new_id(),
                        user_id=user_id,
                        query_id=qid,
                        schema_version=c.schema_version,
                        conditions=stored,
                        conditions_fingerprint=fp,
                        fingerprint_version=FINGERPRINT_VERSION,
                        start_label=sl,
                        end_label=el,
                        status="searching",
                        search_run_id=run,
                        search_lease_expires_at=now + SEARCH_LEASE,
                        plan_ordered=False,
                        revision=0,
                        created_at=now,
                        updated_at=now,
                    )
                    s.add(h)
                else:
                    if h.status == "searching" and h.search_lease_expires_at and h.search_lease_expires_at > now:
                        raise ApiError(409, "SEARCH_IN_PROGRESS", "此查詢正在搜尋中", extra={"history_id": str(h.id)})
                    h.status, h.search_run_id = "searching", run
                    h.search_lease_expires_at, h.updated_at = now + SEARCH_LEASE, now
                await s.flush()
                return h.id, run
        except IntegrityError:
            if attempt == 0:
                continue
            raise
    raise RuntimeError("unreachable")


async def finish_search(
    factory, history_id: uuid.UUID, run_id: uuid.UUID, status: str, reasons: dict | None, now: datetime
) -> bool:
    async with factory() as s, s.begin():
        r = await s.execute(
            update(History)
            .where(History.id == history_id, History.search_run_id == run_id)
            .values(status=status, search_run_id=None, search_lease_expires_at=None, reasons=reasons, updated_at=now)
        )
        return rowcount(r) == 1


async def update_plan(
    factory,
    user_id: uuid.UUID,
    qid: uuid.UUID,
    c: Conditions,
    stops: list[StoredStop],
    ordered: bool,
    expected_revision: int | None,
    now: datetime,
    reasons: dict | None,
) -> tuple[uuid.UUID, int] | None:
    check_key_time(qid, now)
    async with factory() as s, s.begin():
        await lock_active_user(s, user_id)
        sid, eid, _ = await member_endpoint_ids(s, user_id, c)
        fp = conditions_fingerprint(c, sid, eid)
        op = await _operation(s, user_id, qid, fp, c, now, create=False)
        h = (
            await s.execute(
                select(History).where(History.user_id == user_id, History.query_id == qid).with_for_update()
            )
        ).scalar()
        if h is None and op is None:
            return None
        if h is None:
            raise ApiError(409, "HISTORY_DELETED", "此查詢的歷史已不存在，請建立新查詢")
        if op is None:
            raise ApiError(409, "OPERATION_EXPIRED", "此查詢的操作期限已過，請建立新查詢")
        if h.conditions_fingerprint != fp:
            raise ApiError(409, "QUERY_CONDITIONS_CONFLICT", "條件已改變，請以新查詢送出")
        if expected_revision is None:
            raise ApiError(
                409, "REVISION_REQUIRED", "更新既有歷史需提供 expected_revision", extra={"current_revision": h.revision}
            )
        if expected_revision != h.revision:
            raise ApiError(
                409,
                "REVISION_CONFLICT",
                "行程已在其他分頁或裝置更新，請重新整理頁面後再試。",
                extra={"current_revision": h.revision},
            )
        await s.execute(delete(HistoryStop).where(HistoryStop.history_id == h.id))
        for i, st in enumerate(stops):
            s.add(
                HistoryStop(
                    history_id=h.id,
                    order_index=i,
                    place_id=st.place_id,
                    stay_minutes=st.stay_minutes,
                    stay_source=st.stay_source,
                    day_index=0,
                    selected_google_place_id=st.google_place_id,
                )
            )
        h.revision += 1
        h.plan_ordered = ordered
        h.updated_at = now
        if reasons is not None:
            h.reasons = reasons
        await s.flush()
        return h.id, h.revision


async def precheck_revision(factory, user_id: uuid.UUID, qid: uuid.UUID, expected_revision: int | None) -> None:
    """付費外部呼叫前的快速檢查（避免必定失敗的請求耗用額度）；寫入時仍於交易內再檢查一次。"""
    async with factory() as s:
        h = (
            await s.execute(select(History.revision).where(History.user_id == user_id, History.query_id == qid))
        ).first()
        op = (
            await s.execute(
                select(QueryOperation.state).where(QueryOperation.user_id == user_id, QueryOperation.query_id == qid)
            )
        ).scalar()
    if op == "deleted":
        raise ApiError(409, "HISTORY_DELETED", "此查詢的歷史已刪除，請建立新查詢")
    if h is None:
        return
    if expected_revision is None:
        raise ApiError(
            409, "REVISION_REQUIRED", "更新既有歷史需提供 expected_revision", extra={"current_revision": h.revision}
        )
    if expected_revision != h.revision:
        raise ApiError(
            409,
            "REVISION_CONFLICT",
            "行程已在其他分頁或裝置更新，請重新整理頁面後再試。",
            extra={"current_revision": h.revision},
        )


async def guest_import(
    factory, user_id: uuid.UUID, qid: uuid.UUID, c: Conditions, stops: list[StoredStop], ordered: bool, now: datetime
) -> tuple[History, bool]:
    """訪客中途登入：以同一 query_id 建立 guest_imported 歷史；不接受客戶端自報執行結果或可行性。"""
    check_key_time(qid, now)
    async with factory() as s, s.begin():
        await lock_active_user(s, user_id)
        sid, eid, stored = await member_endpoint_ids(s, user_id, c)
        fp = conditions_fingerprint(c, sid, eid)
        existing = (
            await s.execute(
                select(History).where(History.user_id == user_id, History.query_id == qid).with_for_update()
            )
        ).scalar()
        if existing is not None:
            if existing.conditions_fingerprint != fp:
                raise ApiError(409, "QUERY_CONDITIONS_CONFLICT", "同一 query_id 已有不同條件的歷史")
            return existing, False
        await _operation(s, user_id, qid, fp, c, now, create=True)
        sl, el = _labels(c)
        h = History(
            id=new_id(),
            user_id=user_id,
            query_id=qid,
            schema_version=c.schema_version,
            conditions=stored,
            conditions_fingerprint=fp,
            fingerprint_version=FINGERPRINT_VERSION,
            start_label=sl,
            end_label=el,
            status="guest_imported",
            plan_ordered=ordered,
            revision=0,
            created_at=now,
            updated_at=now,
        )
        s.add(h)
        await s.flush()
        for i, st in enumerate(stops):
            s.add(
                HistoryStop(
                    history_id=h.id,
                    order_index=i,
                    place_id=st.place_id,
                    stay_minutes=st.stay_minutes,
                    stay_source=st.stay_source,
                    day_index=0,
                    selected_google_place_id=st.google_place_id,
                )
            )
        await s.flush()
        return h, True


def encode_cursor(created_at: datetime, rid: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{rid}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cur: str) -> tuple[datetime, uuid.UUID]:
    try:
        pad = "=" * (-len(cur) % 4)
        ts, rid = base64.urlsafe_b64decode(cur + pad).decode().split("|")
        return datetime.fromisoformat(ts), uuid.UUID(rid)
    except Exception as e:
        raise ApiError(422, "INVALID_CURSOR", "cursor 不合法") from e


def keyset(model, cursor: str | None):
    if cursor is None:
        return None
    ts, rid = decode_cursor(cursor)
    return or_(model.created_at < ts, and_(model.created_at == ts, model.id < rid))


async def list_histories(
    factory, user_id: uuid.UUID, cursor: str | None, limit: int
) -> tuple[list[History], str | None]:
    async with factory() as s:
        q = select(History).where(History.user_id == user_id)
        k = keyset(History, cursor)
        if k is not None:
            q = q.where(k)
        rows = list(
            (await s.execute(q.order_by(History.created_at.desc(), History.id.desc()).limit(limit + 1))).scalars()
        )
    nxt = encode_cursor(rows[limit - 1].created_at, rows[limit - 1].id) if len(rows) > limit else None
    return rows[:limit], nxt


async def get_history(factory, user_id: uuid.UUID, hid: uuid.UUID) -> tuple[History, list[HistoryStop]]:
    async with factory() as s:
        h = (await s.execute(select(History).where(History.id == hid, History.user_id == user_id))).scalar()
        if h is None:
            raise ApiError(404, "HISTORY_NOT_FOUND", "找不到此歷史")
        stops = list(
            (
                await s.execute(
                    select(HistoryStop).where(HistoryStop.history_id == hid).order_by(HistoryStop.order_index)
                )
            ).scalars()
        )
        return h, stops


async def delete_history_rows(s: AsyncSession, user_id: uuid.UUID, hid: uuid.UUID) -> bool:
    """單筆刪除：刪歷史（收藏不受影響，外鍵 SET NULL），query_operation 標 deleted 保留至窗口結束。"""
    h = (
        await s.execute(select(History).where(History.id == hid, History.user_id == user_id).with_for_update())
    ).scalar()
    if h is None:
        return False
    await s.execute(
        update(QueryOperation)
        .where(QueryOperation.user_id == user_id, QueryOperation.query_id == h.query_id)
        .values(state="deleted")
    )
    await s.execute(update(Favorite).where(Favorite.source_history_id == hid).values(source_history_id=None))
    await s.execute(delete(History).where(History.id == hid))
    return True
