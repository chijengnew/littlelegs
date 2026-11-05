"""會員帳號與地點詳情（獨立來源，不呼叫 Google）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, Response

from app.api.deps import _bearer, client_ip, get_state, limit, optional_user, require_user
from app.api.problems import DELETE_CONFLICT, EMAIL_NOT_VERIFIED, conflict, not_found
from app.api.v1.histories import _op_id
from app.api.v1.models import DELETION_ACCEPTED, DeletionResponse, MeResponse, PlaceDetailResponse
from app.api.v1.saved import parse_path_id
from app.db.models import User
from app.domain.ranking import estimated_age_range
from app.errors import ApiError
from app.ratelimit import QuotaExceeded
from app.services import deletion, registration
from app.services.places import place_detail
from app.services.users import CurrentUser
from app.state import AppState

router = APIRouter(tags=["account"])
GENERAL = [Depends(limit("general"))]


@router.get("/me", response_model=MeResponse, dependencies=GENERAL, responses=EMAIL_NOT_VERIFIED)
async def me(user: CurrentUser = Depends(require_user), st: AppState = Depends(get_state)) -> dict:
    async with st.factory() as s:
        u = await s.get(User, user.id)
    if u is None:
        raise ApiError(401, "AUTH_REAUTH_REQUIRED", "會員不存在")
    return {"id": str(u.id), "status": u.status, "locale": u.locale}


@router.delete(
    "/me",
    response_model=DeletionResponse,
    responses={**not_found("USER_NOT_FOUND", "找不到會員資料"), **DELETE_CONFLICT, **DELETION_ACCEPTED},
    summary="刪除帳號：需最近 5 分鐘內重新登入；回 202 表示已接受未完成",
)
async def delete_me(
    request: Request,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
    st: AppState = Depends(get_state),
) -> dict:
    token = await _token_with_ip_limit(request, authorization, st)
    out = await deletion.request_account_deletion(st, token, _op_id(idempotency_key))
    response.status_code = 200 if out.completed else 202
    return {"operation_id": out.operation_id, "status": "completed" if out.completed else "accepted", "kind": "account"}


@router.delete(
    "/me/registration",
    status_code=204,
    responses=conflict("REGISTRATION_COMPLETED", "Email 已完成驗證，註冊已完成，無法取消註冊"),
    summary=(
        "取消註冊：只限 Email 未驗證、僅密碼登入且沒有會員資料的帳號；"
        "刪除 Firebase 帳號，不建立會員業務資料（仍做 IP 限流與會員確認）"
    ),
)
async def cancel_registration(
    request: Request, authorization: str | None = Header(default=None), st: AppState = Depends(get_state)
) -> Response:
    token = await _token_with_ip_limit(request, authorization, st)
    await registration.cancel_registration(st, token)
    return Response(status_code=204)


async def _token_with_ip_limit(request: Request, authorization: str | None, st: AppState) -> str:
    """取出 Bearer Token 並只做 IP 入站限流。"""
    token = _bearer(authorization)
    if token is None:
        raise ApiError(401, "AUTH_REQUIRED", "此功能需要登入")
    try:
        await st.limiter.inbound("general", client_ip(request), None)
    except QuotaExceeded as e:
        raise ApiError(429, "RATE_LIMITED", "請求過於頻繁，請稍後再試", headers={"Retry-After": "60"}) from e
    return token


@router.get(
    "/deletions/{operation_id}",
    response_model=DeletionResponse,
    dependencies=GENERAL,
    responses=not_found("DELETION_NOT_FOUND", "找不到此刪除請求"),
)
async def deletion_status(
    operation_id: str, user: CurrentUser = Depends(require_user), st: AppState = Depends(get_state)
) -> dict:
    return await deletion.deletion_status(st, user.id, parse_path_id(operation_id, "operation_id"))


@router.get(
    "/places/{place_id}",
    response_model=PlaceDetailResponse,
    dependencies=GENERAL,
    responses=not_found("PLACE_NOT_FOUND", "找不到此地點"),
    tags=["places"],
    summary="地點詳情：獨立來源欄位、屬性證據與來源追溯（不含 Google 內容）",
)
async def get_place(
    place_id: str, user: CurrentUser | None = Depends(optional_user), st: AppState = Depends(get_state)
) -> dict:
    pid = parse_path_id(place_id, "place_id")
    async with st.factory() as s:
        d = await place_detail(s, pid)
    if d is None:
        raise ApiError(404, "PLACE_NOT_FOUND", "找不到此地點")
    p = d["place"]
    rng = estimated_age_range(p.primary_type) if not p.age_ranges else None
    d["place"] = {
        "place_id": p.ref,
        "kind": p.kind,
        "name": p.name,
        "address": p.address,
        "city": p.city,
        "location": {"lat": p.lat, "lng": p.lon, "source": "open_data"} if user is not None else None,
        "primary_type": p.primary_type,
        "types": p.types,
        "indoor": {"value": p.indoor, "confirmation": p.indoor_confirmation},
        "facilities": {f: {"status": s_, "confirmation": c} for f, (s_, c) in p.facilities.items()},
        "source_stay_minutes": p.source_stay_minutes,
        "age_range": None if rng is None else {"min_age": rng[0], "max_age": rng[1], "confirmation": "estimated"},
        "removed": p.removed,
        "removed_note": "已自來源下架，資料未驗證" if p.removed else None,
    }
    return d
