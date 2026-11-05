"""API 請求／回應模型（Pydantic 為最終驗證；前端 Zod 僅即時回饋）。

條件輸入規則在此驗證；相對日期（今天起 30 天內）與「出發必須晚於 now」需要伺服器時鐘，
另由 app.domain.validation 以注入的 clock 檢查。
"""

from __future__ import annotations

import re
from datetime import date, time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ids import is_canonical_uuid4, is_canonical_uuid7
from app.timeutil import on_tick, parse_hhmm

SCHEMA_VERSION: Literal[1] = 1

FacilityPref = Literal["stroller_friendly", "nursing_room", "family_toilet"]
TypePref = Literal[
    "parent_child_center",
    "zoo",
    "aquarium",
    "museum",
    "tourism_factory",
    "amusement_park",
    "industry_heritage",
    "diy_workshop",
    "env_edu",
    "nature_center",
    "farm",
    "park_playground",
    "library",
    "arts_venue",
    "night_market",
    "old_street",
    "street",
    "temple",
    "heritage",
    "indigenous",
    "hakka",
    "beach",
    "hot_spring",
    "bike_path",
    "trail",
    "shopping",
    "shop_cafe",
    "waterfront",
    "sports",
    "campus",
    "scenic_ride",
    "public_art",
    "community",
    "visitor_center",
    "station",
    "landmark",
    "nature",
    "other",
]
MAX_DEFAULT_STAY = 120
TYPE_DEFAULT_STAY = {
    "parent_child_center": 90,
    "zoo": 120,
    "aquarium": 90,
    "museum": 60,
    "tourism_factory": 60,
    "amusement_park": 120,
    "industry_heritage": 45,
    "diy_workshop": 60,
    "env_edu": 60,
    "nature_center": 45,
    "farm": 90,
    "park_playground": 45,
    "library": 45,
    "arts_venue": 45,
    "night_market": 60,
    "old_street": 60,
    "street": 30,
    "temple": 30,
    "heritage": 45,
    "indigenous": 60,
    "hakka": 45,
    "beach": 90,
    "hot_spring": 90,
    "bike_path": 60,
    "trail": 60,
    "shopping": 60,
    "shop_cafe": 30,
    "waterfront": 45,
    "sports": 60,
    "campus": 45,
    "scenic_ride": 45,
    "public_art": 30,
    "community": 45,
    "visitor_center": 30,
    "station": 30,
    "landmark": 30,
    "nature": 60,
    "other": 45,
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _uuid7_str(v: str) -> str:
    if not is_canonical_uuid7(v):
        raise ValueError("必須是小寫、含連字號的標準 UUIDv7")
    return v


class TimeWindow(StrictModel):
    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def _tick(cls, v: str) -> str:
        t = parse_hhmm(v)
        if not on_tick(t):
            raise ValueError("時間必須是 15 分鐘刻度")
        return v

    @model_validator(mode="after")
    def _order(self) -> TimeWindow:
        if parse_hhmm(self.start) >= parse_hhmm(self.end):
            raise ValueError("開始時間必須早於結束時間")
        return self

    @property
    def t_start(self) -> time:
        return parse_hhmm(self.start)

    @property
    def t_end(self) -> time:
        return parse_hhmm(self.end)


class PlaceRefEndpoint(StrictModel):
    type: Literal["place_ref"]
    place_id: str

    @field_validator("place_id")
    @classmethod
    def _pid(cls, v: str) -> str:
        return _uuid7_str(v)


class GooglePlaceEndpoint(StrictModel):
    """其他地點（例如家）：只保存 Place ID 與內部端點參照，不保存 Google 名稱、地址或座標。"""

    type: Literal["google_place"]
    google_place_id: str = Field(min_length=1, max_length=255)
    endpoint_id: str | None = None
    label: str | None = Field(default=None, min_length=1, max_length=20)

    @field_validator("endpoint_id")
    @classmethod
    def _eid(cls, v: str | None) -> str | None:
        return None if v is None else _uuid7_str(v)


class DeviceCoordinateEndpoint(StrictModel):
    type: Literal["device_coordinate"]
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)
    label: str | None = Field(default=None, min_length=1, max_length=20)


Endpoint = Annotated[PlaceRefEndpoint | GooglePlaceEndpoint | DeviceCoordinateEndpoint, Field(discriminator="type")]


class Conditions(StrictModel):
    schema_version: Literal[1] = SCHEMA_VERSION
    date: date
    depart_time: str
    return_time: str
    start: Endpoint
    end: Endpoint | None = None
    travel_mode: Literal["drive"] = "drive"
    children_ages: list[Annotated[int, Field(ge=0, le=18)]] = Field(min_length=1, max_length=5)
    nap: TimeWindow | None = None
    lunch: TimeWindow | None = None
    dinner: TimeWindow | None = None
    rain_indoor_only: bool = False
    facility_prefs: list[FacilityPref] = Field(default_factory=list, max_length=3)
    type_prefs: list[TypePref] = Field(default_factory=list, max_length=len(TYPE_DEFAULT_STAY))

    @field_validator("depart_time", "return_time")
    @classmethod
    def _tick(cls, v: str) -> str:
        if not on_tick(parse_hhmm(v)):
            raise ValueError("時間必須是 15 分鐘刻度")
        return v

    @model_validator(mode="after")
    def _cross(self) -> Conditions:
        dep, ret = parse_hhmm(self.depart_time), parse_hhmm(self.return_time)
        if (ret.hour * 60 + ret.minute) - (dep.hour * 60 + dep.minute) < 120:
            raise ValueError("回程時間至少比出發晚 120 分鐘，且需為同一天")
        if self.nap and not (dep <= self.nap.t_start and self.nap.t_end <= ret):
            raise ValueError("午睡時段必須整段位於行程時窗內")
        for name, w in (("lunch", self.lunch), ("dinner", self.dinner)):
            if w is None:
                continue
            if not (dep <= w.t_start and w.t_end <= ret):
                raise ValueError(f"{name} 用餐時窗必須位於行程時窗內")
            if (w.t_end.hour * 60 + w.t_end.minute) - (w.t_start.hour * 60 + w.t_start.minute) < 60:
                raise ValueError(f"{name} 用餐時窗至少 60 分鐘")
        return self

    @property
    def end_or_start(self):
        return self.end if self.end is not None else self.start

    @property
    def t_depart(self) -> time:
        return parse_hhmm(self.depart_time)

    @property
    def t_return(self) -> time:
        return parse_hhmm(self.return_time)


class StopIn(StrictModel):
    place_id: str
    stay_minutes: int | None = Field(default=None, ge=15, le=360)

    @field_validator("place_id")
    @classmethod
    def _pid(cls, v: str) -> str:
        return _uuid7_str(v)

    @field_validator("stay_minutes")
    @classmethod
    def _mult(cls, v: int | None) -> int | None:
        if v is not None and v % 15 != 0:
            raise ValueError("停留時間必須是 15 分鐘倍數")
        return v


def _unique_stops(v: list[StopIn]) -> list[StopIn]:
    ids = [s.place_id for s in v]
    if len(set(ids)) != len(ids):
        raise ValueError("選取的停留景點不可重複")
    return v


class CandidateSearchIn(StrictModel):
    query_id: str
    conditions: Conditions

    @field_validator("query_id")
    @classmethod
    def _qid(cls, v: str) -> str:
        return _uuid7_str(v)


class PlanIn(StrictModel):
    """排序（auto）與可行性檢查（manual 順序）共用。"""

    query_id: str
    conditions: Conditions
    stops: list[StopIn] = Field(min_length=1, max_length=5)
    expected_revision: int | None = Field(default=None, ge=0)

    @field_validator("query_id")
    @classmethod
    def _qid(cls, v: str) -> str:
        return _uuid7_str(v)

    @field_validator("stops")
    @classmethod
    def _uniq(cls, v: list[StopIn]) -> list[StopIn]:
        return _unique_stops(v)


class GuestImportIn(StrictModel):
    query_id: str
    conditions: Conditions
    stops: list[StopIn] = Field(default_factory=list, max_length=5)
    ordered: bool = False
    searched: bool = True

    @field_validator("query_id")
    @classmethod
    def _qid(cls, v: str) -> str:
        return _uuid7_str(v)

    @field_validator("stops")
    @classmethod
    def _uniq(cls, v: list[StopIn]) -> list[StopIn]:
        return _unique_stops(v)


class FavoriteIn(StrictModel):
    conditions: Conditions
    stops: list[StopIn] = Field(min_length=1, max_length=5)
    saved_as: Literal["plan", "unverified", "infeasible"] = "plan"
    source_history_id: str | None = None

    @field_validator("stops")
    @classmethod
    def _uniq(cls, v: list[StopIn]) -> list[StopIn]:
        return _unique_stops(v)

    @field_validator("source_history_id")
    @classmethod
    def _h(cls, v: str | None) -> str | None:
        return None if v is None else _uuid7_str(v)


FeedbackType = Literal["bug", "place_data", "suggestion", "other"]
FeedbackSource = Literal["planner", "place_detail", "saved_detail", "footer", "other"]
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class FeedbackIn(StrictModel):
    type: FeedbackType
    rating: int | None = Field(default=None, ge=1, le=5)
    content: str = Field(min_length=1, max_length=1000)
    contact_email: str | None = Field(default=None, max_length=254)
    source_page: FeedbackSource = "other"
    place_id: str | None = None

    @field_validator("contact_email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        if v is not None and not _EMAIL.match(v):
            raise ValueError("聯絡信箱格式不正確")
        return v

    @field_validator("place_id")
    @classmethod
    def _pid(cls, v: str | None) -> str | None:
        return None if v is None else _uuid7_str(v)

    @model_validator(mode="after")
    def _place_only_for_place_data(self) -> FeedbackIn:
        if self.place_id is not None and self.type != "place_data":
            raise ValueError("只有景點資料錯誤回報可以附上景點")
        return self


class PlaceSearchIn(StrictModel):
    q: str = Field(min_length=1, max_length=50)
    kind: Literal["attraction", "lodging"] | None = None
    limit: int = Field(default=10, ge=1, le=20)


class AutocompleteIn(StrictModel):
    input: str = Field(min_length=2, max_length=100)
    session_token: str

    @field_validator("session_token")
    @classmethod
    def _tok(cls, v: str) -> str:
        if not is_canonical_uuid4(v):
            raise ValueError("session_token 必須是小寫標準 UUIDv4")
        return v


class ResolveIn(StrictModel):
    google_place_id: str = Field(min_length=1, max_length=255)
    session_token: str

    @field_validator("session_token")
    @classmethod
    def _tok(cls, v: str) -> str:
        if not is_canonical_uuid4(v):
            raise ValueError("session_token 必須是小寫標準 UUIDv4")
        return v
