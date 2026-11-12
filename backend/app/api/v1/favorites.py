"""收藏：不可編輯、不可命名，只能刪除或另存。建立以 Idempotency-Key（UUIDv7）去重。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Response

from app.api.deps import app_check, get_state, limit, require_user
from app.api.problems import DELETE_CONFLICT, not_found
from app.api.v1.histories import _op_id
from app.api.v1.models import (
    DELETION_ACCEPTED,
    DeletionResponse,
    FavoriteCreateResponse,
    FavoriteItem,
    FavoriteList,
    RecheckResponse,
)
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
from app.db.models import Favorite, FavoriteStop
from app.domain.schemas import FavoriteIn
from app.services import deletion
from app.services import favorites as fav_svc
from app.services.users import CurrentUser
from app.state import AppState

router = APIRouter(prefix="/favorites", tags=["favorites"])
GENERAL = [Depends(limit("general"))]
FAVORITE_NOT_FOUND = not_found("FAVORITE_NOT_FOUND", "找不到此收藏")
NOTICE = {
    "plan": "已保存計畫，未於儲存時重新驗證",
    "unverified": "已保存為未驗證計畫，未於儲存時重新驗證",
    "infeasible": "已保存為不可行計畫，未於儲存時重新驗證",
}


async def _item(st: AppState, f: Favorite, stops=None, names: dict[str, str] | None = None) -> dict:
    if names is None:
        names = await place_names(st, [f.conditions])
    start_name, end_name = endpoint_place_names(f.conditions, names)
    d: dict[str, Any] = {
        "id": str(f.id),
        "saved_as": f.saved_as,
        "conditions": f.conditions,
        "start_label": f.start_label,
        "end_label": f.end_label,
        "start_place_name": start_name,
        "end_place_name": end_name,
        "source_history_id": None if f.source_history_id is None else str(f.source_history_id),
        "notice": NOTICE[f.saved_as],
        "created_at": f.created_at.isoformat(),
    }
    if stops is not None:
        d["stops"] = await stops_out(st, stops, f.reasons)
        d["start_location"], d["end_location"] = await endpoint_locations(st, f.conditions)
        d["start_endpoint"], d["end_endpoint"] = await endpoint_navigation(st, f.conditions, f.start_label, f.end_label)
    return d


@router.post(
    "",
    response_model=FavoriteCreateResponse,
    dependencies=GENERAL,
    responses={201: {"model": FavoriteCreateResponse, "description": "已建立新收藏（200 表示回傳既有的同內容收藏）"}},
    summary="收藏目前計畫（不另查付費 API；unverified／infeasible 須使用者明確選擇保存方式）",
)
async def create_favorite(
    body: FavoriteIn,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    user: CurrentUser = Depends(require_user),
    st: AppState = Depends(get_state),
) -> dict:
    res = await fav_svc.create(st.factory, user.id, _op_id(idempotency_key), body, st.clock())
    _, stops = await fav_svc.get_favorite(st.factory, user.id, res.favorite.id)
    response.status_code = 201 if res.created else 200
    return {
        "favorite": await _item(st, res.favorite, stops),
        "created": res.created,
        "notice": NOTICE[res.favorite.saved_as],
    }


@router.get("", response_model=FavoriteList, dependencies=GENERAL)
async def list_favorites(
    cursor: str | None = Query(default=None, max_length=200),
    limit_: int = Query(default=20, ge=1, le=50, alias="limit"),
    user: CurrentUser = Depends(require_user),
    st: AppState = Depends(get_state),
) -> dict:
    rows, nxt = await fav_svc.list_favorites(st.factory, user.id, cursor, limit_)
    names = await place_names(st, [f.conditions for f in rows])
    previews = await stop_previews(st, FavoriteStop, "favorite_id", [f.id for f in rows])
    items = [await _item(st, f, names=names) | {"stop_previews": previews.get(f.id, [])} for f in rows]
    return {"items": items, "next_cursor": nxt}


@router.get("/{favorite_id}", response_model=FavoriteItem, dependencies=GENERAL, responses=FAVORITE_NOT_FOUND)
async def get_favorite(
    favorite_id: str, user: CurrentUser = Depends(require_user), st: AppState = Depends(get_state)
) -> dict:
    f, stops = await fav_svc.get_favorite(st.factory, user.id, parse_path_id(favorite_id, "favorite_id"))
    return await _item(st, f, stops)


@router.post(
    "/{favorite_id}/recheck",
    response_model=RecheckResponse,
    dependencies=[Depends(app_check), Depends(limit("paid"))],
    responses=FAVORITE_NOT_FOUND,
    summary="開啟收藏的重新檢查：原出發時間已過或超出今天起 7 天內時不重算",
)
async def recheck_favorite(
    favorite_id: str, user: CurrentUser = Depends(require_user), st: AppState = Depends(get_state)
) -> dict:
    f, stops = await fav_svc.get_favorite(st.factory, user.id, parse_path_id(favorite_id, "favorite_id"))
    return await recheck(st, user, f"favorite:{f.id}", f.conditions, stops)


@router.delete(
    "/{favorite_id}",
    response_model=DeletionResponse,
    dependencies=GENERAL,
    responses={**not_found("FAVORITE_NOT_FOUND", "找不到此紀錄"), **DELETE_CONFLICT, **DELETION_ACCEPTED},
    summary="取消收藏；所有指向此收藏的舊建立操作永久失效",
)
async def delete_favorite(
    favorite_id: str,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    user: CurrentUser = Depends(require_user),
    st: AppState = Depends(get_state),
) -> dict:
    fid = parse_path_id(favorite_id, "favorite_id")
    out = await deletion.request_record_deletion(st, user.id, "favorite", fid, _op_id(idempotency_key))
    response.status_code = 200 if out.completed else 202
    return {"operation_id": out.operation_id, "status": "completed" if out.completed else "accepted"}
