"""探險護照：到訪紀錄（蓋章）。只給已驗證 Email、狀態正常的會員；均以 Token 對應會員並檢查擁有權。

公開的 GET /v1/places/{id} 不混入會員資料；景點詳情另以 GET /v1/check-ins?place_id= 查本人狀態。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Response

from app.api.deps import app_check, get_state, limit, require_user
from app.api.problems import DELETE_CONFLICT, forbidden, not_found
from app.api.v1.explorer_models import CheckInCreateResponse, CheckInList
from app.api.v1.histories import _op_id
from app.api.v1.models import DELETION_ACCEPTED, DeletionResponse
from app.api.v1.saved import parse_path_id
from app.domain.stamping import CheckInIn
from app.services import check_ins as svc
from app.services import deletion
from app.services.users import CurrentUser
from app.state import AppState

router = APIRouter(prefix="/check-ins", tags=["explorer"])
GENERAL = [Depends(limit("general"))]


def _iso(d) -> str | None:
    return None if d is None else d.isoformat()


def check_in_out(v: svc.CheckInView) -> dict:
    ci, p = v.check_in, v.place
    return {
        "id": str(ci.id),
        "place": {
            "place_id": str(p.place_id),
            "name": p.name,
            "primary_type": p.primary_type,
            "city": p.city,
            "removed": p.removed,
        },
        "verification_method": ci.verification_method,
        "visited_at": _iso(ci.visited_at),
        "verified_at": _iso(ci.verified_at),
    }


@router.post(
    "",
    response_model=CheckInCreateResponse,
    dependencies=[Depends(app_check), Depends(limit("stamp"))],
    responses={
        201: {"model": CheckInCreateResponse, "description": "已建立新的到訪紀錄（200 表示升級或已有紀錄）"},
        **forbidden("APP_CHECK_REQUIRED", "缺少 App Check Token"),
        **not_found("PLACE_NOT_FOUND", "找不到此地點"),
    },
    summary="蓋章：建立手動紀錄、建立定位核對，或把原手動紀錄升級為定位核對（不降級）",
    description=(
        "定位核對的座標與精確度只在本次請求比較，不保存。"
        "同一 Idempotency-Key 重送時，回傳與第一次相同的狀態碼與 outcome。"
        "可能的錯誤代碼："
        "LOCATION_INACCURATE、LOCATION_TOO_FAR、PLACE_NOT_STAMPABLE、PLACE_NO_COORDINATES（422）；"
        "PLACE_REMOVED、IDEMPOTENCY_CONFLICT、OPERATION_CANCELLED、OPERATION_EXPIRED、KEY_TIME_INVALID（409）；"
        "EMAIL_NOT_VERIFIED、APP_CHECK_REQUIRED、APP_CHECK_FAILED、ACCOUNT_DELETING（403）；RATE_LIMITED（429）。"
    ),
)
async def create_check_in(
    body: CheckInIn,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    user: CurrentUser = Depends(require_user),
    st: AppState = Depends(get_state),
) -> dict:
    res = await svc.create(st.factory, user.id, _op_id(idempotency_key), body, st.clock(), st.settings.stamping)
    response.status_code = 201 if res.outcome == "created" else 200
    return {"check_in": check_in_out(res.view), "outcome": res.outcome}


@router.get("", response_model=CheckInList, dependencies=GENERAL, summary="本人的到訪紀錄（新到舊）與數量")
async def list_check_ins(
    cursor: str | None = Query(default=None, max_length=200),
    limit_: int = Query(default=20, ge=1, le=50, alias="limit"),
    place_id: str | None = Query(default=None, description="只看這個景點的本人紀錄（景點詳情顯示是否已蓋章）"),
    user: CurrentUser = Depends(require_user),
    st: AppState = Depends(get_state),
) -> dict:
    pid = None if place_id is None else parse_path_id(place_id, "place_id")
    views, nxt = await svc.list_check_ins(st.factory, user.id, cursor, limit_, pid)
    return {
        "items": [check_in_out(v) for v in views],
        "next_cursor": nxt,
        "counts": await svc.counts(st.factory, user.id),
    }


@router.delete(
    "/{check_in_id}",
    response_model=DeletionResponse,
    dependencies=GENERAL,
    responses={**not_found("CHECK_IN_NOT_FOUND", "找不到此紀錄"), **DELETE_CONFLICT, **DELETION_ACCEPTED},
    summary="刪除單筆到訪紀錄；任務進度隨之重算，指向此紀錄的舊蓋章操作永久失效",
)
async def delete_check_in(
    check_in_id: str,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    user: CurrentUser = Depends(require_user),
    st: AppState = Depends(get_state),
) -> dict:
    cid = parse_path_id(check_in_id, "check_in_id")
    out = await deletion.request_record_deletion(st, user.id, "check_in", cid, _op_id(idempotency_key))
    response.status_code = 200 if out.completed else 202
    return {"operation_id": out.operation_id, "status": "completed" if out.completed else "accepted"}
