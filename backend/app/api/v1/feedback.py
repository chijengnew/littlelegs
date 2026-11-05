"""使用者回饋：訪客與會員皆可送出；驗 App Check，每 IP 另有回饋專用上限。

不看登入身分、不保存會員關聯；回應不回傳內容，也不把內容或信箱寫入應用日誌。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import app_check, feedback_limit, get_state
from app.api.v1.models import FeedbackResponse
from app.domain.schemas import FeedbackIn
from app.services import feedback as svc
from app.state import AppState

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=201,
    dependencies=[Depends(app_check), Depends(feedback_limit)],
    summary="送出使用者回饋",
)
async def create_feedback(body: FeedbackIn, st: AppState = Depends(get_state)) -> dict:
    await svc.create(st.factory, body, st.clock())
    return {"status": "received"}
