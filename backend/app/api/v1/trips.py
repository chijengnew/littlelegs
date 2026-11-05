"""候選搜尋、排序、可行性檢查（訪客與會員皆可）。

含孩子資料與精確位置的查詢一律 POST body，不放 URL。皆驗 App Check 並受付費查詢類入站限流。
完成檢查但行程為 infeasible／unverified 屬業務結果，以 200 回傳。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import app_check, get_state, limit, optional_user
from app.api.v1.models import CandidateResponse, PlanResponse
from app.domain.schemas import CandidateSearchIn, PlanIn
from app.services import planning
from app.services.users import CurrentUser
from app.state import AppState

router = APIRouter(prefix="/trips", tags=["trips"])
PAID = [Depends(app_check), Depends(limit("paid"))]


@router.post(
    "/candidates",
    response_model=CandidateResponse,
    dependencies=PAID,
    summary="候選搜尋（30 km 直線粗篩、最多 15 筆，另列終點附近旅宿）",
)
async def candidates(
    body: CandidateSearchIn, user: CurrentUser | None = Depends(optional_user), st: AppState = Depends(get_state)
) -> dict:
    return await planning.candidate_search(st, user, body.query_id, body.conditions)


@router.post("/sort", response_model=PlanResponse, dependencies=PAID, summary="自動排序（枚舉至多 120 種排列）")
async def sort(
    body: PlanIn, user: CurrentUser | None = Depends(optional_user), st: AppState = Depends(get_state)
) -> dict:
    return await planning.plan(st, user, body.query_id, body.conditions, body.stops, "auto", body.expected_revision)


@router.post(
    "/check", response_model=PlanResponse, dependencies=PAID, summary="依使用者順序與停留時間檢查可行性（不重新排序）"
)
async def check(
    body: PlanIn, user: CurrentUser | None = Depends(optional_user), st: AppState = Depends(get_state)
) -> dict:
    return await planning.plan(st, user, body.query_id, body.conditions, body.stops, "manual", body.expected_revision)
