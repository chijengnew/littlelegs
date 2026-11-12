"""沿途天氣分區：起點、景點與終點依直線距離分成最多 6 區，每區查一次 Google 每日預報。

- 依呼叫端給的順序放入地點；與最近一區的第一個地點相距 10 km 內就併入，否則開新區。
- 已有 6 區時，其餘地點併入最近的一區，不再多查。
- 區名取區內地址最常見的「縣市＋鄉鎮市區」；沒有可辨識的地址時為 None。
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from app.geo import haversine_m

AREA_RADIUS_M = 10_000
MAX_AREAS = 6

_DISTRICT = re.compile(r"^(\S{2,3}?[市縣])(\S{1,4}?[區鄉鎮市])")


def district_of(address: str | None, city: str | None = None) -> str | None:
    """從地址取出「縣市＋鄉鎮市區」；開頭的郵遞區號與「臺灣」會先去掉，認不出時改用城市欄位。"""
    rest = re.sub(r"^\d{3,6}\s*", "", (address or "").strip())
    rest = re.sub(r"^(台灣|臺灣)", "", rest)
    m = _DISTRICT.match(rest)
    if m:
        return m.group(1) + m.group(2)
    return city or None


@dataclass
class AreaPoint:
    key: str
    lat: float
    lon: float
    district: str | None = None


@dataclass
class Area:
    lat: float
    lon: float
    keys: list[str] = field(default_factory=list)
    districts: list[str] = field(default_factory=list)

    @property
    def label(self) -> str | None:
        if not self.districts:
            return None
        return Counter(self.districts).most_common(1)[0][0]


def group_points(points: list[AreaPoint], radius_m: float = AREA_RADIUS_M, max_areas: int = MAX_AREAS) -> list[Area]:
    areas: list[Area] = []
    for p in points:
        near = min(areas, key=lambda a: haversine_m(a.lat, a.lon, p.lat, p.lon), default=None)
        if near is None or (haversine_m(near.lat, near.lon, p.lat, p.lon) > radius_m and len(areas) < max_areas):
            near = Area(p.lat, p.lon)
            areas.append(near)
        near.keys.append(p.key)
        if p.district:
            near.districts.append(p.district)
    return areas
