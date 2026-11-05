"""年齡判斷、候選排序與推薦原因。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.domain.schemas import MAX_DEFAULT_STAY, TYPE_DEFAULT_STAY

AGE_BANDS = ((0, 2), (3, 6), (7, 11), (12, 15), (16, 18))

FIT_CONFIRMED = 3.0
FIT_NEUTRAL = 1.0
TYPE_AGE_FIT: dict[str, tuple[int, int, int, int, int]] = {
    "parent_child_center": (2, 2, 0, 0, 0),
    "park_playground": (2, 2, 2, 1, 0),
    "zoo": (1, 2, 2, 1, 1),
    "aquarium": (1, 2, 2, 1, 1),
    "nature_center": (1, 2, 2, 1, 1),
    "farm": (1, 2, 2, 1, 1),
    "campus": (1, 2, 2, 1, 1),
    "tourism_factory": (0, 2, 2, 1, 1),
    "amusement_park": (0, 2, 2, 2, 1),
    "library": (1, 2, 2, 2, 2),
    "beach": (1, 2, 2, 2, 2),
    "waterfront": (1, 2, 2, 2, 2),
    "scenic_ride": (1, 2, 2, 2, 2),
    "public_art": (1, 2, 2, 2, 2),
    "diy_workshop": (0, 1, 2, 2, 1),
    "env_edu": (0, 1, 2, 2, 1),
    "museum": (0, 1, 2, 2, 2),
    "industry_heritage": (0, 1, 2, 2, 2),
    "night_market": (0, 1, 2, 2, 2),
    "old_street": (0, 1, 2, 2, 2),
    "street": (0, 1, 2, 2, 2),
    "heritage": (0, 1, 2, 2, 2),
    "indigenous": (0, 1, 2, 2, 2),
    "hakka": (0, 1, 2, 2, 2),
    "bike_path": (0, 1, 2, 2, 2),
    "trail": (0, 1, 2, 2, 2),
    "sports": (0, 1, 2, 2, 2),
    "nature": (0, 1, 2, 2, 2),
    "arts_venue": (0, 1, 1, 2, 2),
    "hot_spring": (0, 1, 1, 2, 2),
    "shopping": (1, 1, 1, 2, 2),
    "shop_cafe": (1, 1, 1, 2, 2),
}
INFANT_FACILITIES = ("nursing_room", "family_toilet")
INFANT_FACILITY_BONUS = 0.5
AGE_FIT_DISTANCE_M = 5000.0


def estimated_age_range(primary_type: str | None) -> tuple[int, int] | None:
    """類型的估計適合年齡：分數 2 的分層範圍；沒有估計的類型回 None。"""
    fit = TYPE_AGE_FIT.get(primary_type or "")
    if fit is None:
        return None
    high = [band for band, score in zip(AGE_BANDS, fit, strict=True) if score == 2]
    return high[0][0], high[-1][1]


def _child_fit(place: Any, age: int) -> float:
    band = next(i for i, (lo, hi) in enumerate(AGE_BANDS) if lo <= age <= hi)
    fit = TYPE_AGE_FIT.get(getattr(place, "primary_type", None) or "")
    score = FIT_NEUTRAL if fit is None else float(fit[band])
    if band == 0 and any(place.facilities.get(f, ("unknown",))[0] == "yes" for f in INFANT_FACILITIES):
        score += INFANT_FACILITY_BONUS
    return score


def age_fit_score(place: Any, ages: Sequence[int]) -> float:
    """多位孩子取最低分（全部孩子都適合才算高分）。"""
    return min(_child_fit(place, a) for a in ages)


def age_status(ages: Sequence[int], ranges: list[tuple[int, int, str]], exclusions: list[tuple[int, int]]) -> str:
    """回傳 all_ok / unsuitable / unknown。

    - 已知排除區間包含任一孩子 → unsuitable。
    - 有已確認的適用區間集合（不連續區間分列，不合併成單一 min/max）：每位孩子須落在其中任一區間；
      任一位落在所有已確認區間之外 → unsuitable（來源已知限制未涵蓋）。
    - 沒有已確認區間 → unknown（由 evaluate 改用本站估計，不算已確認）。
    """
    for a in ages:
        if any(lo <= a <= hi for lo, hi in exclusions):
            return "unsuitable"
    confirmed = [(lo, hi) for lo, hi, c in ranges if c == "confirmed"]
    if not confirmed:
        return "unknown"
    for a in ages:
        if not any(lo <= a <= hi for lo, hi in confirmed):
            return "unsuitable"
    return "all_ok"


def default_stay(place, override: int | None) -> tuple[int, str]:
    """停留時間：使用者覆寫 → 來源建議（已取整，預設上限 120 分鐘） → 主要類型預設。"""
    if override is not None:
        return override, "user"
    if place.source_stay_minutes:
        return min(int(place.source_stay_minutes), MAX_DEFAULT_STAY), "source"
    return TYPE_DEFAULT_STAY.get(place.primary_type or "other", 60), "type_default"


@dataclass
class CandidateEval:
    place: Any
    distance_m: float
    age: str
    age_fit: float = FIT_NEUTRAL
    age_range: tuple[int, int] | None = None
    age_match: bool = False
    facility_hits: list[str] = field(default_factory=list)
    type_hit: bool = False
    indoor_state: str = "unknown"
    hours: Any = None


def evaluate(
    place: Any, distance_m: float, ages: Sequence[int], facility_prefs: Sequence[str], type_prefs: Sequence[str]
) -> CandidateEval:
    ev = CandidateEval(place, distance_m, age_status(ages, place.age_ranges, place.age_exclusions))
    if ev.age == "all_ok":
        ev.age_fit, ev.age_match = FIT_CONFIRMED, True
    elif ev.age == "unknown":
        ev.age_fit = age_fit_score(place, ages)
        ev.age_range = estimated_age_range(getattr(place, "primary_type", None))
        if ev.age_range is not None:
            ev.age = "estimated"
            ev.age_match = all(ev.age_range[0] <= a <= ev.age_range[1] for a in ages)
    ev.facility_hits = sorted(f for f in set(facility_prefs) if place.facilities.get(f, ("unknown",))[0] == "yes")
    ev.type_hit = bool(set(type_prefs) & set(place.types))
    if place.indoor == "indoor":
        ev.indoor_state = "indoor_confirmed" if place.indoor_confirmation == "confirmed" else "indoor_inferred"
    elif place.indoor in ("outdoor", "mixed"):
        ev.indoor_state = "not_indoor"
    return ev


def adjusted_distance_m(ev: CandidateEval) -> float:
    """排序用距離：實際直線距離加上年齡分數的換算（只用於排序，不顯示）。"""
    return ev.distance_m + (2.0 - ev.age_fit) * AGE_FIT_DISTANCE_M


def initial_rank_key(ev: CandidateEval):
    """初排：設施命中數多、類型命中、年齡分數換算後的距離近、內部 ID 穩定。"""
    return (
        -len(ev.facility_hits),
        0 if ev.type_hit else 1,
        adjusted_distance_m(ev),
        ev.place.id.bytes,
    )


def rerank_key(ev: CandidateEval):
    """前 15 名內重排：偏好設施數、偏好類型、年齡分數換算後的距離、內部 ID。"""
    return initial_rank_key(ev)


def reasons_and_warnings(
    ev: CandidateEval, *, weather_status: str, rain_checked: bool, nearby_m: float = 5000, hours_checked: bool = True
) -> tuple[list[str], list[str]]:
    """hours_checked=False：候選階段未查營業時間，改提示排序／檢查時確認。"""
    reasons, warnings = [], []
    if ev.age_match:
        reasons.append("age_match")
    if ev.facility_hits:
        reasons.append("facility_match")
    if ev.type_hit:
        reasons.append("type_match")
    if ev.distance_m <= nearby_m:
        reasons.append("nearby")
    if rain_checked and weather_status == "triggered" and ev.indoor_state.startswith("indoor"):
        reasons.append("indoor_match")
    if ev.indoor_state == "indoor_inferred" and rain_checked:
        warnings.append("indoor_inferred")
    if rain_checked and weather_status == "unverified":
        warnings.append("weather_unverified")
    hs = getattr(ev.hours, "status", "unknown")
    if not hours_checked:
        warnings.append("hours_checked_when_planning")
    elif hs == "unknown":
        warnings.append("hours_unknown")
    elif hs == "provisional":
        warnings.append("special_hours_unverified")
    warnings.append("stay_estimated")
    return reasons, warnings


def persistable_reasons(reasons: list[str], start_coord_source: str) -> list[str]:
    keep = {"age_match", "facility_match", "type_match"}
    if start_coord_source in ("open_data", "device"):
        keep.add("nearby")
    return [r for r in reasons if r in keep]


REASON_TEMPLATES_ZH = {
    "age_match": "適合孩子的年齡",
    "indoor_match": "室內場所，符合下雨只排室內",
    "facility_match": "有你選的設施：{facilities}",
    "type_match": "符合你偏好的景點類型",
    "nearby": "距離起點較近（直線距離，非開車距離）",
}
WARNING_TEMPLATES_ZH = {
    "hours_unknown": "營業時間未確認，請出發前自行確認",
    "hours_checked_when_planning": "營業時間會在排序或檢查行程時確認",
    "special_hours_unverified": "特殊營業時間未確認，暫以一般營業時間安排",
    "weather_unverified": "天氣無法確認，不能視為不會下雨",
    "stay_estimated": "停留時間為估計值",
    "indoor_inferred": "室內屬性依類型推定，非場勘確認",
    "travel_unavailable": "車程無法取得，時間軸未驗證",
    "search_incomplete": "排序搜尋未完成，未宣稱為最佳順序",
    "place_removed": "地點已自來源下架，資料未驗證",
}
