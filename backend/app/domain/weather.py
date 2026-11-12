"""降水判定。每一區（見 app.domain.weather_areas）各自判定；是「降水機率」（可能含雪／雨雪），不是確定會下雨。

- 取與行程時窗重疊的日間／夜間區間（以回應 interval 為準）：出遊日日間、出遊日夜間、前一日夜間。
- 觸發值＝重疊區間有效降水機率最大值；≥60% 觸發「只排室內」。
- 任一重疊區間缺漏／無效／未涵蓋：已取得區間 ≥60% 仍觸發；否則為 unverified，並列出未涵蓋時段。
- 缺欄位、越界或互相矛盾 → 該區間未知，不以 0 代替。
- 結果不持久化。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from app.timeutil import TPE, local_dt

THRESHOLD = 60
MAX_FORECAST_OFFSET = 9


@dataclass
class WeatherPart:
    start: datetime
    end: datetime
    percent: int | None
    ptype: str | None
    label: str


@dataclass
class WeatherJudgement:
    status: str
    max_percent: int | None = None
    parts: list[WeatherPart] = field(default_factory=list)
    uncovered: list[tuple[datetime, datetime]] = field(default_factory=list)
    note: str | None = None

    @property
    def indoor_only(self) -> bool:
        return self.status == "triggered"


def request_params(trip_date: date, today: date) -> dict | None:
    """回傳 Weather daily forecast 請求參數；超出涵蓋（今天起第 10 天以後或過去）回 None，不呼叫。"""
    k = (trip_date - today).days
    if k < 0 or k > MAX_FORECAST_OFFSET:
        return None
    return {"days": k + 1, "pageSize": 10}


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(TPE)
    except ValueError:
        return None


def _part(raw: dict | None, label: str) -> WeatherPart | None:
    if not isinstance(raw, dict):
        return None
    iv = raw.get("interval") or {}
    st, en = _parse_ts(iv.get("startTime")), _parse_ts(iv.get("endTime"))
    if st is None or en is None or en <= st:
        return None
    prob = (raw.get("precipitation") or {}).get("probability") or {}
    pct = prob.get("percent")
    ptype = prob.get("type")
    valid = isinstance(pct, int) and not isinstance(pct, bool) and 0 <= pct <= 100
    return WeatherPart(st, en, pct if valid else None, ptype if isinstance(ptype, str) else None, label)


def judge(
    forecast_days: list[dict] | None, trip_date: date, depart: time, ret: time, requested: bool = True
) -> WeatherJudgement:
    if not requested:
        return WeatherJudgement("unverified", note="出遊日超出天氣預報範圍（今天起 10 天內），未查詢")
    if forecast_days is None:
        return WeatherJudgement("unverified", note="天氣服務失敗或回應無效")
    w0, w1 = local_dt(trip_date, depart), local_dt(trip_date, ret)
    parts: list[WeatherPart] = []
    for d in forecast_days:
        if not isinstance(d, dict):
            continue
        for key, label in (("daytimeForecast", "日間"), ("nighttimeForecast", "夜間")):
            p = _part(d.get(key), label)
            if p is None:
                continue
            if p.end > w0 and p.start < w1:
                parts.append(p)
    valid_parts = sorted((p for p in parts if p.percent is not None), key=lambda p: p.start)
    uncovered: list[tuple[datetime, datetime]] = []
    cur = w0
    for p in valid_parts:
        if p.start > cur:
            uncovered.append((cur, min(p.start, w1)))
        cur = max(cur, p.end)
        if cur >= w1:
            break
    if cur < w1:
        uncovered.append((cur, w1))
    mx = max((p.percent for p in valid_parts if p.percent is not None), default=None)
    if mx is not None and mx >= THRESHOLD:
        return WeatherJudgement("triggered", mx, parts, uncovered)
    if not uncovered:
        return WeatherJudgement("not_triggered", mx, parts, [])
    return WeatherJudgement("unverified", mx, parts, uncovered, note="部分行程時段沒有有效預報，不能視為未下雨")


def describe_uncovered(j: WeatherJudgement) -> list[str]:
    return [f"{a.strftime('%H:%M')}–{b.strftime('%H:%M')}" for a, b in j.uncovered]


def official_parts(d: date) -> tuple[tuple[datetime, datetime], tuple[datetime, datetime]]:
    return (
        (local_dt(d, time(7)), local_dt(d, time(19))),
        (local_dt(d, time(19)), local_dt(d + timedelta(days=1), time(7))),
    )
