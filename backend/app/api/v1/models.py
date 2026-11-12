"""API 回應模型（供 OpenAPI 與前端 openapi-typescript 產生型別）。

每個顯示值的來源（open_data／manual／google／system）與確認程度分開表示；回應另附 field_sources 對照表。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.schemas import Conditions

Confirmation = Literal["confirmed", "inferred", "estimated", "unknown"]


class Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Coded(Out):
    code: str
    message: str


class Location(Out):
    lat: float
    lng: float
    source: Literal["open_data", "google", "device"]
    persist: bool | None = None


class FeedbackResponse(Out):
    status: Literal["received"]


class Coordinate(Out):
    lat: float
    lng: float


class EndpointOut(Out):
    type: Literal["place_ref", "google_place", "device_coordinate"]
    label: str | None = None
    place_id: str | None = None
    removed: bool | None = None
    name: str | None = Field(default=None, description="本專案地點的開放資料名稱，供導航連結")
    address: str | None = Field(default=None, description="本專案地點的開放資料地址；沒有可用 Place ID 時供導航連結")
    google_place_id: str | None = Field(
        default=None, description="Google 地點選取的 Place ID；本專案地點只回傳查核接受的 Place ID"
    )
    endpoint_id: str | None = None
    coordinate: Coordinate | None = Field(default=None, description="裝置座標（使用者自己的條件），供導航連結")
    location: Location | None = None


class FacilityState(Out):
    status: Literal["yes", "no", "unknown"]
    confirmation: Confirmation


class IndoorState(Out):
    value: Literal["indoor", "outdoor", "mixed"] | None
    confirmation: Confirmation


class StayOut(Out):
    minutes: int
    source: Literal["user", "source", "type_default"]
    estimated: bool


class HoursOut(Out):
    status: Literal["known", "provisional", "unknown", "closed_permanently", "closed_temporarily"]
    intervals: list[list[str | None]]
    notes: list[str]
    source: Literal["google"]


class WeatherPartOut(Out):
    label: str
    start: str | None
    end: str | None
    percent: int | None
    type: str | None


class WeatherAreaOut(Out):
    label: str | None = Field(description="區內地址最常見的縣市＋鄉鎮市區；認不出時為 null")
    roles: list[Literal["start", "end"]] = Field(description="此區包含起點及／或終點")
    status: Literal["triggered", "not_triggered", "unverified"]
    max_precipitation_percent: int | None
    parts: list[WeatherPartOut]
    uncovered: list[str]
    note: str | None


class WeatherOut(Out):
    status: Literal["triggered", "not_triggered", "unverified", "not_requested"] = Field(
        description="勾選「下雨只排室內」時為各區的綜合判定；沒勾選時為 not_requested，天氣只供顯示"
    )
    max_precipitation_percent: int | None
    threshold_percent: int
    location: Literal["start"]
    note: str | None
    explanation: str
    parts: list[WeatherPartOut]
    uncovered: list[str]
    source: Literal["google"]
    rain_filter: bool = Field(default=False, description="是否勾選「下雨只排室內」")
    areas: list[WeatherAreaOut] = Field(
        default_factory=list, description="沿途分區天氣：地點彼此 10 km 內算同一區，最多 6 區，第一區含起點"
    )


class MapHints(Out):
    mode: Literal["google_map", "locked_illustration"]
    message: str | None = None
    connect_line: bool | None = None
    line_note: str | None = None


class AgeRangeOut(Out):
    min_age: int
    max_age: int
    confirmation: Confirmation


class CandidateOut(Out):
    place_id: str
    google_place_id: str | None
    name: str
    address: str | None
    city: str | None
    distance_m: int
    distance_note: str
    primary_type: str | None
    types: dict[str, Confirmation]
    indoor: IndoorState
    facilities: dict[str, FacilityState]
    age: Literal["all_ok", "estimated", "unknown"] = Field(
        description="all_ok：來源確認全部孩子適合；estimated：本站依類型估計；unknown：類型沒有明顯親子屬性"
    )
    age_range: AgeRangeOut | None = Field(default=None, description="本站估計的適合年齡（只影響排序與顯示）")
    default_stay: StayOut
    reasons: list[Coded]
    warnings: list[Coded]
    location: Location | None = None
    weather_area: int | None = Field(default=None, description="此景點所在的 weather.areas 索引")


class LodgingItem(Out):
    place_id: str
    name: str
    address: str | None
    distance_m: int
    distance_note: str
    family_facilities: list[Literal["crib", "baby_bathtub", "kids_play_area"]]
    label: Literal["有親子設施資訊", "親子設施未確認"]
    location: Location | None = None


class LodgingOut(Out):
    items: list[LodgingItem]
    empty: bool
    note: str | None


class HistoryRef(Out):
    id: str
    status: str | None = None
    revision: int | None


class CandidateResponse(Out):
    query_id: str
    operation: Literal["ok", "partial", "no_results"]
    start: EndpointOut
    end: EndpointOut
    weather: WeatherOut | None
    candidates: list[CandidateOut]
    candidate_count: int
    lodging: LodgingOut
    history: HistoryRef | None
    map: MapHints
    field_sources: dict[str, str]
    attributions: list[str]
    notices: list[str]


class TimelineItem(Out):
    type: Literal["attraction", "meal", "rest", "move"]
    start: str | None
    end: str | None
    estimated: bool
    source: Literal["system", "google"]
    place_id: str | None = None
    name: str | None = None
    from_: str | None = None
    to: str | None = None
    duration_s: int | None = None
    distance_m: int | None = None
    meal: Literal["lunch", "dinner"] | None = None
    at: str | None = None
    reason: str | None = None
    note: str | None = None

    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, alias_generator=lambda f: "from" if f == "from_" else f
    )


class PlanStopOut(Out):
    place_id: str
    name: str
    address: str | None = None
    google_place_id: str | None = Field(default=None, description="查核接受的 Place ID，供導航連結；其他狀態為 null")
    primary_type: str | None = Field(default=None, description="主要類型，供準備清單判斷海灘、溫泉、步道等提醒")
    stay_minutes: int
    stay_source: Literal["user", "source", "type_default"]
    estimated: bool
    hours: HoursOut | None
    removed: bool
    location: Location | None = None


class SearchInfo(Out):
    complete: bool
    optimal_claimed: bool
    permutations_evaluated: int
    note: str


ViolationCode = Literal[
    "AGE_UNSUITABLE",
    "INDOOR_REQUIRED",
    "PLACE_CLOSED",
    "MEAL_NAP_CONFLICT",
    "MEALS_OVERLAP",
    "RETURN_TIME_EXCEEDED",
    "OPENING_HOURS",
    "MEAL_UNSCHEDULABLE",
    "NAP_CONFLICT",
    "TIME_WINDOW_INSUFFICIENT",
    "ROUTE_NOT_FOUND",
    "PROVISIONAL_HOURS_CONFLICT",
]


class Violation(Out):
    """違規明細；依 code 只填相關欄位，其餘為 null。"""

    code: ViolationCode
    place_ref: str | None = Field(
        default=None, description="涉及的景點（AGE_UNSUITABLE、INDOOR_REQUIRED、PLACE_CLOSED、OPENING_HOURS）"
    )
    status: Literal["closed_permanently", "closed_temporarily"] | None = Field(
        default=None, description="PLACE_CLOSED：營業狀態"
    )
    until: str | None = Field(default=None, description="RETURN_TIME_EXCEEDED：最晚抵達終點時間")
    intervals: list[list[str]] | None = Field(default=None, description="OPENING_HOURS：當日營業區間 [開始, 結束]")
    windows: list[list[str]] | None = Field(default=None, description="MEAL_UNSCHEDULABLE：[餐別, 開始, 結束]")
    nap: list[str] | None = Field(default=None, description="NAP_CONFLICT：午睡時段 [開始, 結束]")
    meal: str | None = Field(default=None, description="MEAL_NAP_CONFLICT、MEALS_OVERLAP：涉及的餐別")
    combined: bool | None = Field(default=None, description="true：須與另一項條件一起放寬才可行")


class PlanResponse(Out):
    query_id: str
    mode: Literal["auto", "manual"]
    operation: Literal["ok", "partial"]
    feasibility: Literal["feasible", "infeasible", "unverified"]
    feasibility_note: str
    order: list[str]
    stops: list[PlanStopOut]
    timeline: list[TimelineItem]
    warnings: list[Coded]
    violation_codes: list[ViolationCode]
    violations: list[Violation]
    suggest_remove: list[str]
    search: SearchInfo
    start: EndpointOut
    end: EndpointOut
    weather: WeatherOut | None
    history: HistoryRef | None
    map: MapHints
    field_sources: dict[str, str]
    attributions: list[str]
    notices: list[str]


class RecheckResponse(Out):
    """rechecked=False 時只帶原因；True 時帶完整當次檢查（plan 欄位）。"""

    rechecked: bool
    reason: str | None = None
    message: str | None = None
    checked_at: str | None = None
    plan: PlanResponse | None = None


class PlaceSummary(Out):
    place_id: str
    kind: Literal["attraction", "lodging"]
    name: str
    address: str | None
    city: str | None
    primary_type: str | None


class PlaceSearchResponse(Out):
    items: list[PlaceSummary]


class Suggestion(Out):
    google_place_id: str
    text: str | None


class AutocompleteResponse(Out):
    suggestions: list[Suggestion]
    attribution: Literal["Google Maps"]


class ResolveResponse(Out):
    google_place_id: str
    in_service_area: bool
    endpoint_id: str | None
    location: Location | None


class SavedStop(Out):
    order_index: int
    place_id: str
    name: str | None
    address: str | None = None
    google_place_id: str | None = Field(default=None, description="查核接受的 Place ID，供導航連結；其他狀態為 null")
    primary_type: str | None = Field(default=None, description="主要類型，供準備清單判斷海灘、溫泉、步道等提醒")
    stay_minutes: int
    stay_source: Literal["user", "source", "type_default"]
    removed: bool
    reasons_at_save: list[Coded]
    location: Location | None = Field(default=None, description="開放資料座標，供會員地圖使用；地點已不存在時為 null")


class StopPreview(Out):
    name: str | None
    primary_type: str | None


STOP_PREVIEWS_DESC = "只在列表提供：依順序的景點名稱與主要類型，供卡片標題與類型圖示；開啟單筆時改看 stops"
START_PLACE_NAME_DESC = "起點為本專案地點（place_ref）時的開放資料名稱；其他類型為 null，改用 start_label"
END_PLACE_NAME_DESC = "終點名稱，規則同 start_place_name；終點同起點時與起點相同"
START_LOCATION_DESC = (
    "只在詳細回應提供，供會員地圖使用：本專案地點為開放資料座標、裝置座標為保存的條件；"
    "Google 地點的座標不保存，為 null（重新檢查後才取得）"
)
END_LOCATION_DESC = "終點座標，規則同 start_location；終點同起點時與起點相同"
START_ENDPOINT_DESC = "只在詳細回應提供，供導航連結：開啟時不呼叫 Google；地點已不存在時為 null"
END_ENDPOINT_DESC = "終點導航資料，規則同 start_endpoint；終點同起點時與起點相同"


class HistoryItem(Out):
    id: str
    query_id: str
    status: str
    revision: int
    plan_ordered: bool
    conditions: Conditions = Field(description="當初保存的條件（與請求格式相同）")
    start_label: str | None
    end_label: str | None
    start_place_name: str | None = Field(default=None, description=START_PLACE_NAME_DESC)
    end_place_name: str | None = Field(default=None, description=END_PLACE_NAME_DESC)
    stops: list[SavedStop] | None = None
    stop_previews: list[StopPreview] | None = Field(default=None, description=STOP_PREVIEWS_DESC)
    start_location: Location | None = Field(default=None, description=START_LOCATION_DESC)
    end_location: Location | None = Field(default=None, description=END_LOCATION_DESC)
    start_endpoint: EndpointOut | None = Field(default=None, description=START_ENDPOINT_DESC)
    end_endpoint: EndpointOut | None = Field(default=None, description=END_ENDPOINT_DESC)
    operation_window_open: bool | None = None
    notice: str | None = None
    created_at: str
    updated_at: str


class HistoryList(Out):
    items: list[HistoryItem]
    next_cursor: str | None


class FavoriteItem(Out):
    id: str
    saved_as: Literal["plan", "unverified", "infeasible"]
    conditions: Conditions = Field(description="當初保存的條件（與請求格式相同）")
    start_label: str | None
    end_label: str | None
    start_place_name: str | None = Field(default=None, description=START_PLACE_NAME_DESC)
    end_place_name: str | None = Field(default=None, description=END_PLACE_NAME_DESC)
    source_history_id: str | None
    stops: list[SavedStop] | None = None
    stop_previews: list[StopPreview] | None = Field(default=None, description=STOP_PREVIEWS_DESC)
    start_location: Location | None = Field(default=None, description=START_LOCATION_DESC)
    end_location: Location | None = Field(default=None, description=END_LOCATION_DESC)
    start_endpoint: EndpointOut | None = Field(default=None, description=START_ENDPOINT_DESC)
    end_endpoint: EndpointOut | None = Field(default=None, description=END_ENDPOINT_DESC)
    notice: str
    created_at: str


class FavoriteCreateResponse(Out):
    favorite: FavoriteItem
    created: bool
    notice: str


class FavoriteList(Out):
    items: list[FavoriteItem]
    next_cursor: str | None


class DeletionResponse(Out):
    operation_id: str
    status: Literal["accepted", "completed"]
    kind: str | None = None
    accepted_at: str | None = None


class MeResponse(Out):
    id: str
    status: str
    locale: str


SourceType = Literal["open_data", "manual"]


class PlaceDetail(Out):
    place_id: str
    kind: Literal["attraction", "lodging"]
    name: str
    address: str | None
    city: str | None
    location: Location | None = Field(description="訪客為 null")
    primary_type: str | None
    types: dict[str, Confirmation]
    indoor: IndoorState
    facilities: dict[str, FacilityState]
    source_stay_minutes: int | None = Field(description="來源建議停留時間（分鐘）")
    age_range: AgeRangeOut | None = Field(default=None, description="本站估計的適合年齡（只影響排序與顯示）")
    removed: bool
    removed_note: str | None


class PlaceSource(Out):
    source_record_id: str
    dataset_key: str
    dataset_title: str
    provider: str | None
    source_url: str
    license: str
    license_status: Literal["verified", "unverified"]
    dataset_updated_at: str | None = Field(description="資料集更新時間（ISO 8601；來源沒標時區就不含時區）")
    record_updated_at: str | None = Field(description="此筆紀錄的更新時間（同上）")
    removed: bool
    name: str
    address: str | None
    display: dict[str, Any] | None = Field(description="來源的顯示用欄位，依資料集而不同")


class TypeEvidence(Out):
    type: str
    confirmation: Confirmation
    source_type: SourceType
    evidence: str | None = Field(description="判斷依據")
    evidence_record_id: str | None = Field(description="依據的來源紀錄 ID（對應 sources[].source_record_id）")
    verified_at: str | None = Field(description="人工確認時間")


class FacilityEvidence(Out):
    facility: str
    status: Literal["yes", "no", "unknown"]
    confirmation: Confirmation
    source_type: SourceType
    evidence: str | None
    evidence_record_id: str | None
    verified_at: str | None


class IndoorEvidence(Out):
    value: Literal["indoor", "outdoor", "mixed"] | None
    confirmation: Confirmation
    source_type: SourceType | None
    evidence: str | None
    evidence_record_id: str | None
    verified_at: str | None


class AgeRangeEvidence(Out):
    min_age: int
    max_age: int
    confirmation: Confirmation
    source_type: SourceType
    evidence: str | None
    evidence_record_id: str | None
    verified_at: str | None


class AgeExclusionEvidence(Out):
    min_age: int
    max_age: int
    source_type: SourceType
    evidence: str | None
    evidence_record_id: str | None
    verified_at: str | None


class PlaceEvidence(Out):
    types: list[TypeEvidence]
    facilities: list[FacilityEvidence]
    indoor: IndoorEvidence | None
    age_ranges: list[AgeRangeEvidence]
    age_exclusions: list[AgeExclusionEvidence] = Field(description="來源已知不適合的年齡")


class PlaceDetailResponse(Out):
    place: PlaceDetail
    sources: list[PlaceSource]
    evidence: PlaceEvidence


DELETION_ACCEPTED: dict[int | str, dict] = {
    202: {"model": DeletionResponse, "description": "已接受刪除，尚未完成；以 /v1/deletions/{operation_id} 查詢進度"}
}
