"""探險護照與任務的回應模型。不含任何座標、精確度或距離。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.api.v1.models import Out


class CheckInPlace(Out):
    place_id: str
    name: str
    primary_type: str | None
    city: str | None
    removed: bool = Field(description="景點已下架：紀錄保留供本人查看，不再新增到訪，也不計入任務")


class CheckInOut(Out):
    id: str
    place: CheckInPlace
    verification_method: Literal["location", "manual"] = Field(
        description="location＝定位核對；manual＝手動紀錄（不算定位成功，不計入任務）"
    )
    visited_at: str = Field(description="首次建立紀錄的時間（UTC，ISO 8601）；不是經核實的實際到訪時間")
    verified_at: str | None = Field(
        description="首次定位核對成功的時間（UTC，ISO 8601）；手動紀錄為 null。定位核對不是不可偽造的到場證明"
    )


class CheckInCreateResponse(Out):
    check_in: CheckInOut
    outcome: Literal["created", "upgraded", "existing"] = Field(
        description="created＝新建立；upgraded＝原手動紀錄升級為定位核對；existing＝已有紀錄，未改動"
    )


class CheckInCounts(Out):
    total: int
    location: int
    manual: int


class CheckInList(Out):
    items: list[CheckInOut]
    next_cursor: str | None
    counts: CheckInCounts = Field(description="本人全部到訪紀錄的數量（不受分頁或 place_id 篩選影響）")


class MissionOut(Out):
    code: str = Field(description="任務代碼；名稱與說明由前端翻譯檔對應")
    kind: Literal["distinct_places"]
    threshold: int
    types: list[str] = Field(description="限定的主要類型代碼；空陣列表示不限類型")
    progress: int = Field(description="目前符合條件的不重複景點數（可能大於門檻）")
    unlocked: bool


class MissionList(Out):
    items: list[MissionOut]
    counted_places: int = Field(description="目前計入任務的不重複景點數：定位核對成功且景點未下架")
