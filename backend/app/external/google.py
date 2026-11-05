"""Google Maps Platform 伺服器端呼叫（Places API (New)、Routes Compute Route Matrix、Weather）。

- 伺服器金鑰只在後端；每個請求明確指定 field mask，不用 *，只取用途所需的最低計費等級欄位。
- 每個請求標明其 Google 計費項目（SKU），由 Limiter 依每月免費額度准入。
- 每次實際送出（含重試）前先取得應用層出站額度（Limiter.outbound），准入交易提交後才送出；
  已送出即使失敗也不退款。HTTPX 不使用內建重試，由此統一管理：僅暫時性錯誤重試 1 次，受剩餘期限限制。
- 每 worker 外部併發上限、每次嘗試總期限 10 秒（另設 connect/read/write/pool timeout）、整體期限由 Deadline 控制。
- 回應只供當次處理，不持久化、不寫日誌。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.ratelimit import (
    SKU_AUTOCOMPLETE,
    SKU_FREE,
    SKU_MATRIX_ELEMENTS,
    SKU_PLACE_DETAILS_ENTERPRISE,
    SKU_PLACE_DETAILS_ESSENTIALS,
    SKU_TEXT_SEARCH_PRO,
    SKU_WEATHER,
    Limiter,
)

PLACES = "https://places.googleapis.com/v1"
ROUTES_MATRIX = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
WEATHER_DAYS = "https://weather.googleapis.com/v1/forecast/days:lookup"
TRANSIENT_STATUS = {429, 500, 502, 503, 504}


class Deadline:
    def __init__(self, seconds: float) -> None:
        self._end = time.monotonic() + seconds

    def remaining(self) -> float:
        return max(0.0, self._end - time.monotonic())

    def expired(self) -> bool:
        return self.remaining() <= 0


class GoogleError(Exception):
    def __init__(self, kind: str, detail: str = "") -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind


@dataclass
class MatrixElement:
    status: str
    seconds: int | None
    meters: int | None
    condition: str | None


class GoogleGateway(Protocol):
    async def place_location(
        self, place_id: str, deadline: Deadline, session_token: str | None = None
    ) -> tuple[float, float]: ...

    async def place_hours(self, place_id: str, deadline: Deadline) -> dict: ...

    async def autocomplete(self, text: str, session_token: str, deadline: Deadline) -> list[dict]: ...

    async def route_matrix(
        self, points: list[tuple[float, float]], deadline: Deadline
    ) -> dict[tuple[int, int], MatrixElement]: ...

    async def daily_forecast(
        self, lat: float, lon: float, days: int, page_size: int, deadline: Deadline
    ) -> list[dict] | None: ...

    async def text_search(self, query: str, lat: float, lon: float, deadline: Deadline) -> list[dict]: ...

    async def place_id_only(self, place_id: str, deadline: Deadline) -> str: ...


def _duration_s(v: Any) -> int | None:
    if isinstance(v, str) and v.endswith("s"):
        try:
            return int(round(float(v[:-1])))
        except ValueError:
            return None
    return None


class HttpGoogleGateway:
    def __init__(self, api_key: str, limiter: Limiter, concurrency: int = 4, attempt_timeout_s: float = 10.0) -> None:
        self._key = api_key
        self._lim = limiter
        self._sem = asyncio.Semaphore(concurrency)
        self._attempt = attempt_timeout_s
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=3.0, read=attempt_timeout_s, write=5.0, pool=3.0),
            limits=httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency),
            transport=httpx.AsyncHTTPTransport(retries=0),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        url: str,
        *,
        deadline: Deadline,
        quota: dict,
        field_mask: str | None,
        params: dict | None = None,
        json: Any = None,
    ) -> Any:
        last: Exception | None = None
        for _attempt in range(2):
            if deadline.remaining() < 0.5:
                raise GoogleError("deadline", "整體查詢期限不足")
            await self._lim.outbound(**quota)
            headers = {"X-Goog-Api-Key": self._key}
            if field_mask:
                headers["X-Goog-FieldMask"] = field_mask
            try:
                async with self._sem:
                    resp = await asyncio.wait_for(
                        self._client.request(method, url, params=params, json=json, headers=headers),
                        timeout=min(self._attempt, deadline.remaining()),
                    )
            except (TimeoutError, httpx.TimeoutException, httpx.TransportError) as e:
                last = GoogleError("unavailable", type(e).__name__)
                continue
            if resp.status_code == 404:
                raise GoogleError("not_found", "")
            if resp.status_code in TRANSIENT_STATUS:
                last = GoogleError("unavailable", str(resp.status_code))
                continue
            if resp.status_code in (401, 403):
                raise GoogleError("denied", str(resp.status_code))
            if resp.status_code >= 400:
                raise GoogleError("invalid_request", str(resp.status_code))
            try:
                return resp.json()
            except ValueError as e:
                raise GoogleError("invalid_response", "非 JSON") from e
        raise last or GoogleError("unavailable", "")

    async def place_location(
        self, place_id: str, deadline: Deadline, session_token: str | None = None
    ) -> tuple[float, float]:
        params = {"languageCode": "zh-TW", "regionCode": "TW"}
        if session_token:
            params["sessionToken"] = session_token
        data = await self._request(
            "GET",
            f"{PLACES}/places/{place_id}",
            deadline=deadline,
            quota={"google_requests": 1, "sku": SKU_PLACE_DETAILS_ESSENTIALS},
            field_mask="id,location",
            params=params,
        )
        loc = (data or {}).get("location") or {}
        lat, lon = loc.get("latitude"), loc.get("longitude")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            raise GoogleError("invalid_response", "缺 location")
        return float(lat), float(lon)

    async def place_hours(self, place_id: str, deadline: Deadline) -> dict:
        return await self._request(
            "GET",
            f"{PLACES}/places/{place_id}",
            deadline=deadline,
            quota={"google_requests": 1, "sku": SKU_PLACE_DETAILS_ENTERPRISE},
            field_mask="id,businessStatus,currentOpeningHours,regularOpeningHours",
            params={"languageCode": "zh-TW", "regionCode": "TW"},
        )

    async def autocomplete(self, text: str, session_token: str, deadline: Deadline) -> list[dict]:
        body = {"input": text, "sessionToken": session_token, "includedRegionCodes": ["tw"], "languageCode": "zh-TW"}
        data = await self._request(
            "POST",
            f"{PLACES}/places:autocomplete",
            deadline=deadline,
            quota={"autocomplete": 1, "autocomplete_session": session_token, "sku": SKU_AUTOCOMPLETE},
            field_mask="suggestions.placePrediction.placeId,suggestions.placePrediction.text",
            json=body,
        )
        out = []
        for s in (data or {}).get("suggestions", []):
            pp = s.get("placePrediction") or {}
            if pp.get("placeId"):
                out.append({"google_place_id": pp["placeId"], "text": (pp.get("text") or {}).get("text")})
        return out

    async def route_matrix(
        self, points: list[tuple[float, float]], deadline: Deadline
    ) -> dict[tuple[int, int], MatrixElement]:
        wps = [{"waypoint": {"location": {"latLng": {"latitude": la, "longitude": lo}}}} for la, lo in points]
        n = len(points)
        body = {"origins": wps, "destinations": wps, "travelMode": "DRIVE", "routingPreference": "TRAFFIC_UNAWARE"}
        data = await self._request(
            "POST",
            ROUTES_MATRIX,
            deadline=deadline,
            quota={"google_requests": 1, "matrix_elements": n * n, "sku": SKU_MATRIX_ELEMENTS, "sku_units": n * n},
            field_mask="originIndex,destinationIndex,status,condition,duration,distanceMeters",
            json=body,
        )
        return parse_matrix(data, n)

    async def daily_forecast(
        self, lat: float, lon: float, days: int, page_size: int, deadline: Deadline
    ) -> list[dict] | None:
        params = {
            "location.latitude": lat,
            "location.longitude": lon,
            "days": days,
            "pageSize": page_size,
            "languageCode": "zh-TW",
        }
        data = await self._request(
            "GET",
            WEATHER_DAYS,
            deadline=deadline,
            quota={"google_requests": 1, "sku": SKU_WEATHER},
            field_mask=None,
            params=params,
        )
        fd = (data or {}).get("forecastDays")
        return fd if isinstance(fd, list) else None

    async def text_search(self, query: str, lat: float, lon: float, deadline: Deadline) -> list[dict]:
        body = {
            "textQuery": query,
            "languageCode": "zh-TW",
            "regionCode": "TW",
            "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lon}, "radius": 2000.0}},
        }
        data = await self._request(
            "POST",
            f"{PLACES}/places:searchText",
            deadline=deadline,
            quota={"google_requests": 1, "sku": SKU_TEXT_SEARCH_PRO},
            field_mask="places.id,places.displayName,places.formattedAddress,places.location",
            json=body,
        )
        return (data or {}).get("places", []) or []

    async def place_id_only(self, place_id: str, deadline: Deadline) -> str:
        """Place ID 更新：只取 id（依官方 ID refresh 規則處理費率），仍扣應用呼叫額度。"""
        data = await self._request(
            "GET",
            f"{PLACES}/places/{place_id}",
            deadline=deadline,
            quota={"google_requests": 1, "sku": SKU_FREE},
            field_mask="id",
            params=None,
        )
        pid = (data or {}).get("id")
        if not isinstance(pid, str) or not pid:
            raise GoogleError("invalid_response", "缺 id")
        return pid


def parse_matrix(data: Any, n: int) -> dict[tuple[int, int], MatrixElement]:
    """按 originIndex／destinationIndex 配對，不依回應順序；缺漏／錯誤不當成功。"""
    out: dict[tuple[int, int], MatrixElement] = {}
    if not isinstance(data, list):
        data = []
    for el in data:
        if not isinstance(el, dict):
            continue
        oi, di = el.get("originIndex", 0), el.get("destinationIndex", 0)
        if not (isinstance(oi, int) and isinstance(di, int) and 0 <= oi < n and 0 <= di < n):
            continue
        status = el.get("status") or {}
        code = status.get("code", 0) if isinstance(status, dict) else 0
        cond = el.get("condition")
        secs = _duration_s(el.get("duration"))
        meters = el.get("distanceMeters")
        if code not in (0, None):
            out[(oi, di)] = MatrixElement("unknown", None, None, cond)
        elif cond == "ROUTE_NOT_FOUND":
            out[(oi, di)] = MatrixElement("no_route", None, None, cond)
        elif cond == "ROUTE_EXISTS" and secs is not None:
            out[(oi, di)] = MatrixElement("ok", secs, meters if isinstance(meters, int) else None, cond)
        elif oi == di and secs is not None:
            out[(oi, di)] = MatrixElement("ok", secs, meters if isinstance(meters, int) else 0, cond)
        else:
            out[(oi, di)] = MatrixElement("unknown", None, None, cond)
    for i in range(n):
        for j in range(n):
            out.setdefault((i, j), MatrixElement("unknown", None, None, None))
    return out
