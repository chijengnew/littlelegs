"""任務與徽章：進度與解鎖狀態由後端依目前的定位核對紀錄即時計算，前端不自行決定。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_state, limit, require_user
from app.api.v1.explorer_models import MissionList
from app.domain import missions as defs
from app.services import check_ins as svc
from app.services.users import CurrentUser
from app.state import AppState

router = APIRouter(prefix="/missions", tags=["explorer"])


@router.get(
    "",
    response_model=MissionList,
    dependencies=[Depends(limit("general"))],
    summary="任務進度與已解鎖徽章：只計定位核對成功、未下架的不重複景點；手動紀錄不計入",
)
async def list_missions(user: CurrentUser = Depends(require_user), st: AppState = Depends(get_state)) -> dict:
    places = await svc.mission_places(st.factory, user.id)
    items = []
    for m in defs.MISSIONS:
        n = defs.progress(m, places)
        items.append(
            {
                "code": m.code,
                "kind": m.kind,
                "threshold": m.threshold,
                "types": list(m.types),
                "progress": n,
                "unlocked": n >= m.threshold,
            }
        )
    return {"items": items, "counted_places": len({p.place_id for p in places})}
