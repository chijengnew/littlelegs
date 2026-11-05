"""座標與距離工具。"""

from __future__ import annotations

import math

EARTH_RADIUS_M = 6_371_008.8

TW_LAT_MIN, TW_LAT_MAX = 21.8, 26.5
TW_LON_MIN, TW_LON_MAX = 118.1, 122.2


def in_taiwan(lat: float | None, lon: float | None) -> bool:
    if lat is None or lon is None:
        return False
    return TW_LAT_MIN <= lat <= TW_LAT_MAX and TW_LON_MIN <= lon <= TW_LON_MAX


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """球面直線距離（公尺）。這不是開車距離。"""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def bounding_box(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    """回傳 (lat_min, lat_max, lon_min, lon_max)，供 SQL 先以 bbox 粗篩。"""
    dlat = math.degrees(radius_m / EARTH_RADIUS_M)
    cos_lat = max(0.01, math.cos(math.radians(lat)))
    dlon = math.degrees(radius_m / (EARTH_RADIUS_M * cos_lat))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon
