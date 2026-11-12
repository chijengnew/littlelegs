"""會員歷史：列表、讀取、中途登入匯入、重新檢查、刪除。只給會員，均檢查擁有權。"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Response

from app.api.deps import app_check, get_state, limit, require_user
from app.api.problems import DELETE_CONFLICT, not_found
from app.api.v1.models import DELETION_ACCEPTED, DeletionResponse, HistoryItem, HistoryList, RecheckResponse
from app.api.v1.saved import (
    endpoint_locations,
    endpoint_navigation,
    endpoint_place_names,
    parse_path_id,
    place_names,
    recheck,
    stop_previews,
    stops_out,
)
from app.db.models import History, HistoryStop, QueryOperation
from app.domain.schemas import GuestImportIn
from app.errors import ApiError
from app.ids import parse_uuid7
from app.services import deletion
from app.services import history as history_svc
from app.services.history import StoredStop
from app.services.places import load_places
from app.services.users import CurrentUser
from app.state import AppState

router = APIRouter(prefix="/histories", tags=["histories"])
GENERAL = [Depends(limit("general"))]
HISTORY_NOT_FOUND = not_found("HISTORY_NOT_FOUND", "找不到此歷史")


def _iso(d) -> str:
    return d.isoformat()


async def _item(st: AppState, h: History, stops=None, now=None, names: dict[str, str] | None = None) -> dict:
    if names is None:
        names = await place_names(st, [h.conditions])
    start_name, end_name = endpoint_place_names(h.conditions, names)
    d: dict[str, Any] = {
        "id": str(h.id),
        "query_id": str(h.query_id),
        "status": h.status,
        "revision": h.revision,
        "plan_ordered": h.plan_ordered,
        "conditions": h.conditions,
        "start_label": h.start_label,
        "end_label": h.end_label,
        "start_place_name": start_name,
        "end_place_name": end_name,
        "created_at": _iso(h.created_at),
        "updated_at": _iso(h.updated_at),
    }
    if stops is not None:
        d["stops"] = await stops_out(st, stops, h.reasons)
        d["start_location"], d["end_location"] = await endpoint_locations(st, h.conditions)
        d["start_endpoint"], d["end_endpoint"] = await endpoint_navigation(st, h.conditions, h.start_label, h.end_label)
        async with st.factory() as s:
            op = await s.get(QueryOperation, (h.user_id, h.query_id))
        d["operation_window_open"] = bool(op and op.state == "created" and now < op.expires_at)
        d["notice"] = "保存的是當時的條件與計畫，不保證重現當時的 Google 清單、營業資訊或車程"
    return d


@router.get("", response_model=HistoryList, dependencies=GENERAL)
async def list_histories(
    cursor: str | None = Query(default=None, max_length=200),
    limit_: int = Query(default=20, ge=1, le=50, alias="limit"),
    user: CurrentUser = Depends(require_user),
    st: AppState = Depends(get_state),
) -> dict:
    rows, nxt = await history_svc.list_histories(st.factory, user.id, cursor, limit_)
    names = await place_names(st, [h.conditions for h in rows])
    previews = await stop_previews(st, HistoryStop, "history_id", [h.id for h in rows])
    items = [await _item(st, h, names=names) | {"stop_previews": previews.get(h.id, [])} for h in rows]
    return {"items": items, "next_cursor": nxt}


@router.get("/{history_id}", response_model=HistoryItem, dependencies=GENERAL, responses=HISTORY_NOT_FOUND)
async def get_history(
    history_id: str, user: CurrentUser = Depends(require_user), st: AppState = Depends(get_state)
) -> dict:
    h, stops = await history_svc.get_history(st.factory, user.id, parse_path_id(history_id, "history_id"))
    return await _item(st, h, stops, st.clock())


@router.post(
    "/guest-import",
    response_model=HistoryItem,
    dependencies=GENERAL,
    responses={201: {"model": HistoryItem, "description": "已建立歷史（200 表示此 query_id 的歷史已存在）"}},
    summary="訪客中途登入：以同一 query_id 建立 guest_imported 歷史（不接受客戶端自報結果）",
)
async def guest_import(
    body: GuestImportIn,
    response: Response,
    user: CurrentUser = Depends(require_user),
    st: AppState = Depends(get_state),
) -> dict:
    if not body.searched:
        raise ApiError(422, "NOT_SEARCHED", "尚未執行候選搜尋，不建立歷史")
    now = st.clock()
    async with st.factory() as s:
        places = await load_places(s, [uuid.UUID(x.place_id) for x in body.stops])
    from app.domain.ranking import default_stay

    stored = []
    for i, x in enumerate(body.stops):
        p = places.get(uuid.UUID(x.place_id))
        if p is None or p.kind != "attraction":
            raise ApiError(422, "STOP_NOT_FOUND", "找不到選取的景點", errors=[{"loc": ["stops", str(i)]}])
        stay, src = default_stay(p, x.stay_minutes)
        stored.append(StoredStop(p.id, stay, src, p.google_place_id))
    h, created = await history_svc.guest_import(
        st.factory, user.id, uuid.UUID(body.query_id), body.conditions, stored, body.ordered and bool(stored), now
    )
    response.status_code = 201 if created else 200
    _, stops = await history_svc.get_history(st.factory, user.id, h.id)
    return await _item(st, h, stops, now)


@router.post(
    "/{history_id}/recheck",
    response_model=RecheckResponse,
    dependencies=[Depends(app_check), Depends(limit("paid"))],
    responses=HISTORY_NOT_FOUND,
    summary="開啟歷史的重新檢查：只更新當次畫面，不改寫原條件或原採用順序",
)
async def recheck_history(
    history_id: str, user: CurrentUser = Depends(require_user), st: AppState = Depends(get_state)
) -> dict:
    h, stops = await history_svc.get_history(st.factory, user.id, parse_path_id(history_id, "history_id"))
    return await recheck(st, user, str(h.query_id), h.conditions, stops)


@router.delete(
    "/{history_id}",
    response_model=DeletionResponse,
    dependencies=GENERAL,
    responses={**not_found("HISTORY_NOT_FOUND", "找不到此紀錄"), **DELETE_CONFLICT, **DELETION_ACCEPTED},
    summary="刪除單筆歷史（收藏不受影響）；Idempotency-Key 為不可重用的刪除操作 ID",
)
async def delete_history(
    history_id: str,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    user: CurrentUser = Depends(require_user),
    st: AppState = Depends(get_state),
) -> dict:
    hid = parse_path_id(history_id, "history_id")
    op = _op_id(idempotency_key)
    out = await deletion.request_record_deletion(st, user.id, "history", hid, op)
    response.status_code = 200 if out.completed else 202
    return {"operation_id": out.operation_id, "status": "completed" if out.completed else "accepted"}


def _op_id(v: str) -> uuid.UUID:
    try:
        return parse_uuid7(v)
    except ValueError as e:
        raise ApiError(
            422,
            "VALIDATION_FAILED",
            "Idempotency-Key 必須是小寫標準 UUIDv7",
            errors=[{"loc": ["header", "Idempotency-Key"], "msg": "invalid uuid7"}],
        ) from e
