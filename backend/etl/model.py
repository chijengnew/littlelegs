"""ETL 中介資料結構。所有欄位皆來自獨立來源（政府開放資料），不含任何 Google 內容。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PRIMARY_TYPE_PRIORITY = (
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
)
PLACE_TYPES = tuple(sorted(PRIMARY_TYPE_PRIORITY))
TYPE_INDOOR = {
    "museum": "indoor",
    "tourism_factory": "indoor",
    "parent_child_center": "indoor",
    "zoo": "outdoor",
    "library": "indoor",
    "arts_venue": "indoor",
    "diy_workshop": "indoor",
    "visitor_center": "indoor",
    "aquarium": "indoor",
    "park_playground": "outdoor",
    "amusement_park": "outdoor",
    "farm": "outdoor",
    "temple": "outdoor",
    "heritage": "outdoor",
    "hot_spring": "outdoor",
    "night_market": "outdoor",
    "old_street": "outdoor",
    "shopping": "outdoor",
    "beach": "outdoor",
    "waterfront": "outdoor",
    "bike_path": "outdoor",
    "trail": "outdoor",
    "nature": "outdoor",
    "shop_cafe": "indoor",
    "street": "outdoor",
    "landmark": "outdoor",
    "scenic_ride": "outdoor",
    "public_art": "outdoor",
    "community": "outdoor",
}

FACILITIES = (
    "stroller_friendly",
    "nursing_room",
    "family_toilet",
    "crib",
    "baby_bathtub",
    "kids_play_area",
    "playground",
)

CONFIRMATIONS = ("confirmed", "inferred", "estimated", "unknown")


@dataclass
class Attr:
    """單一屬性值＋證據。verified_at 只放來源明示的查核日期；開放資料一般為 None。"""

    value: Any
    confirmation: str
    evidence: str
    source_type: str = "open_data"
    verified_at: str | None = None


@dataclass
class SourceRec:
    dataset_key: str
    source_key: str
    name: str
    kind: str
    address: str | None = None
    city: str | None = None
    lat: float | None = None
    lon: float | None = None
    coord_note: str | None = None
    types: dict[str, Attr] = field(default_factory=dict)
    indoor: Attr | None = None
    facilities: dict[str, Attr] = field(default_factory=dict)
    age_ranges: list[tuple[int, int, Attr]] = field(default_factory=list)
    stay_minutes_raw: int | None = None
    service_status: int | None = None
    public_access: bool | None = None
    source_updated_at: str | None = None
    display: dict[str, Any] = field(default_factory=dict)


@dataclass
class FacilityPoint:
    """獨立設施點位（親子廁所、哺乳室）。只有名稱可確認屬於同一場域時才掛到地點。"""

    dataset_key: str
    source_key: str
    facility: str
    venue_name: str
    category: str | None
    lat: float | None
    lon: float | None
    city: str | None
    note: str | None = None


@dataclass
class Exclusion:
    dataset_key: str
    source_key: str
    name: str
    reason: str
