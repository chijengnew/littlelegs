"""業務 API 統一 /v1 前綴（健康檢查與 Firebase /__/auth/ 代理不在此列）。"""

from fastapi import APIRouter

from app.api.problems import common_errors
from app.api.v1 import account, check_ins, endpoints, favorites, feedback, histories, missions, trips

router = APIRouter(prefix="/v1")
for r, app_check, conflict_example, member_only in (
    (trips.router, True, ("DEPARTURE_PASSED", "出發時間已過，請選擇新的時間"), False),
    (endpoints.router, True, ("USER_CREATE_CONFLICT", "請重試"), False),
    (histories.router, False, ("QUERY_CONDITIONS_CONFLICT", "同一 query_id 已有不同條件的歷史"), True),
    (favorites.router, False, ("IDEMPOTENCY_CONFLICT", "同一操作識別碼的內容不同"), True),
    (account.router, False, ("USER_CREATE_CONFLICT", "請重試"), False),
    (check_ins.router, False, ("IDEMPOTENCY_CONFLICT", "同一操作識別碼的內容不同"), True),
    (missions.router, False, ("USER_CREATE_CONFLICT", "請重試"), True),
):
    router.include_router(
        r, responses=common_errors(app_check=app_check, conflict_example=conflict_example, member_only=member_only)
    )
_feedback_errors = common_errors(app_check=True, conflict_example=("USER_CREATE_CONFLICT", "請重試"))
router.include_router(feedback.router, responses={k: v for k, v in _feedback_errors.items() if k not in (401, 409)})
