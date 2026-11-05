"""起訖點選取：本專案地點搜尋（不呼叫 Google）與 Google 地點自動完成／選定解析。

訪客可用、皆驗 App Check；入站限流採「起訖點選取類」每 IP 20 次／分鐘（不占付費查詢類次數）。
自動完成建議與解析座標不持久化；前端顯示建議時須依 Google Maps Platform 政策顯示來源標示。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import app_check, get_state, limit, optional_user
from app.api.problems import not_found
from app.api.v1.models import AutocompleteResponse, PlaceSearchResponse, ResolveResponse
from app.domain.schemas import AutocompleteIn, PlaceSearchIn, ResolveIn
from app.errors import ApiError
from app.external.google import Deadline, GoogleError
from app.geo import in_taiwan
from app.ratelimit import QuotaExceeded, quota_api_error
from app.services import places as places_svc
from app.services.endpoints import find_private_endpoint
from app.services.users import CurrentUser
from app.state import AppState

router = APIRouter(prefix="/endpoints", tags=["endpoints"])
SELECT = [Depends(app_check), Depends(limit("endpoint_select"))]


@router.post(
    "/places/search",
    response_model=PlaceSearchResponse,
    dependencies=SELECT,
    summary="以名稱搜尋本專案地點（景點／旅宿），不呼叫 Google",
)
async def search_places(body: PlaceSearchIn, st: AppState = Depends(get_state)) -> dict:
    async with st.factory() as s:
        rows = await places_svc.search_by_name(s, body.q, body.kind, body.limit)
    return {
        "items": [
            {
                "place_id": p.ref,
                "kind": p.kind,
                "name": p.name,
                "address": p.address,
                "city": p.city,
                "primary_type": p.primary_type,
            }
            for p in rows
        ]
    }


@router.post(
    "/autocomplete",
    response_model=AutocompleteResponse,
    dependencies=SELECT,
    summary="Google 地點自動完成代理（限台灣、zh-TW；每個 session 最多 10 次）",
)
async def autocomplete(body: AutocompleteIn, st: AppState = Depends(get_state)) -> dict:
    if st.google is None:
        raise ApiError(503, "EXTERNAL_UNAVAILABLE", "地點搜尋服務未設定")
    try:
        sugg = await st.google.autocomplete(
            body.input, body.session_token, Deadline(st.settings.limits.attempt_timeout_s)
        )
    except QuotaExceeded as e:
        raise quota_api_error(e) from e
    except GoogleError as e:
        raise ApiError(503, "AUTOCOMPLETE_FAILED", "暫時無法搜尋地點") from e
    return {"suggestions": sugg, "attribution": "Google Maps"}


@router.post(
    "/resolve",
    response_model=ResolveResponse,
    dependencies=SELECT,
    responses=not_found("PLACE_NOT_FOUND", "找不到此地點，請重新選擇"),
    summary="選定建議：以同一 session token 取 Place Details（id、location）並結束 session",
)
async def resolve_selected(
    body: ResolveIn, user: CurrentUser | None = Depends(optional_user), st: AppState = Depends(get_state)
) -> dict:
    if st.google is None:
        raise ApiError(503, "EXTERNAL_UNAVAILABLE", "地點解析服務未設定")
    try:
        lat, lon = await st.google.place_location(
            body.google_place_id, Deadline(st.settings.limits.attempt_timeout_s), session_token=body.session_token
        )
    except QuotaExceeded as e:
        raise quota_api_error(e) from e
    except GoogleError as e:
        if e.kind == "not_found":
            raise ApiError(404, "PLACE_NOT_FOUND", "找不到此地點，請重新選擇") from e
        raise ApiError(503, "ENDPOINT_RESOLVE_FAILED", "暫時無法解析地點") from e
    inside = in_taiwan(lat, lon)
    endpoint_id = None
    if user is not None:
        async with st.factory() as s:
            found = await find_private_endpoint(s, user.id, body.google_place_id)
            endpoint_id = None if found is None else str(found)
    return {
        "google_place_id": body.google_place_id,
        "in_service_area": inside,
        "endpoint_id": endpoint_id,
        "location": {"lat": lat, "lng": lon, "source": "google", "persist": False}
        if (user is not None and inside)
        else None,
    }
