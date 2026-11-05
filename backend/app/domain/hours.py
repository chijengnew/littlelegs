"""營業時間解析。

來源：Places API (New) 的 currentOpeningHours（最多含今天 7 天）與 regularOpeningHours。
- 解析結構化 periods／date；不用 openNow 或本地化文字判斷未來日期。
- 區分欄位缺漏（unknown）與明確空陣列（已知無營業時段）。
- 處理 24 小時營業（只有 open 無 close）、跨午夜與 truncated 邊界。
- 今天起第 7 天以後或缺 currentOpeningHours：以 regularOpeningHours 暫定，標示特殊營業時間未確認（provisional）。
- 結果不持久化。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from app.timeutil import local_dt

CURRENT_HOURS_MAX_OFFSET = 6


def _g_weekday(d: date) -> int:
    return (d.weekday() + 1) % 7


@dataclass
class OpeningInfo:
    status: str
    intervals: list[tuple[datetime, datetime]] = field(default_factory=list)
    business_status: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.status in ("known", "provisional")


def _point_dt(p: dict, anchor: date | None) -> datetime | None:
    """把 period 的 open/close 點轉成當地 datetime。有 date 欄位優先，否則以 anchor 週次推算。"""
    try:
        h, m = int(p.get("hour", 0)), int(p.get("minute", 0))
    except (TypeError, ValueError):
        return None
    if h == 24:
        h, extra = 0, timedelta(days=1)
    else:
        extra = timedelta()
    dd = p.get("date")
    if isinstance(dd, dict) and all(k in dd for k in ("year", "month", "day")):
        try:
            base = date(int(dd["year"]), int(dd["month"]), int(dd["day"]))
        except (TypeError, ValueError):
            return None
        return local_dt(base, time(h, m)) + extra
    if anchor is None or "day" not in p:
        return None
    delta = (int(p["day"]) - _g_weekday(anchor)) % 7
    return local_dt(anchor + timedelta(days=delta), time(h, m)) + extra


def _always_open(periods: list[dict]) -> bool:
    """Google 以「只有 open、沒有 close」的單一 period 表示全天候營業。"""
    return any(isinstance(p, dict) and isinstance(p.get("open"), dict) and p.get("close") is None for p in periods)


def _intervals_from_current(periods: list[dict], target: date) -> list[tuple[datetime, datetime]] | None:
    day0, day1 = local_dt(target, time(0)), local_dt(target + timedelta(days=1), time(0))
    if _always_open(periods):
        return [(day0, day1)]
    out = []
    for per in periods:
        o, c = per.get("open"), per.get("close")
        if not isinstance(o, dict) or not isinstance(c, dict):
            return None
        st, en = _point_dt(o, None), _point_dt(c, None)
        if st is None or en is None:
            return None
        if en <= st:
            en += timedelta(days=7)
        if en > day0 and st < day1:
            out.append((max(st, day0), min(en, day1)))
    return out


def _intervals_from_regular(periods: list[dict], target: date) -> list[tuple[datetime, datetime]] | None:
    day0, day1 = local_dt(target, time(0)), local_dt(target + timedelta(days=1), time(0))
    if _always_open(periods):
        return [(day0, day1)]
    out = []
    for per in periods:
        o, c = per.get("open"), per.get("close")
        if not isinstance(o, dict) or not isinstance(c, dict) or "day" not in o or "day" not in c:
            return None
    for anchor in (target - timedelta(days=1), target):
        for per in periods:
            o, c = per["open"], per["close"]
            if int(o["day"]) != _g_weekday(anchor):
                continue
            st = _point_dt({k: v for k, v in o.items() if k != "date"}, anchor)
            en = _point_dt({k: v for k, v in c.items() if k != "date"}, anchor)
            if st is None or en is None:
                return None
            while en <= st:
                en += timedelta(days=1)
            if en > day0 and st < day1:
                out.append((max(st, day0), min(en, day1)))
    return out


def _merge(iv: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    iv = sorted(iv)
    out: list[tuple[datetime, datetime]] = []
    for s, e in iv:
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def opening_for_date(place: dict | None, target: date, today: date) -> OpeningInfo:
    """place 為當次 Place Details 回應（只含 businessStatus、currentOpeningHours、regularOpeningHours）。"""
    if place is None:
        return OpeningInfo("unknown", notes=["營業資訊取得失敗"])
    bs = place.get("businessStatus")
    if bs == "CLOSED_PERMANENTLY":
        return OpeningInfo("closed_permanently", business_status=bs)
    if bs == "CLOSED_TEMPORARILY":
        return OpeningInfo("closed_temporarily", business_status=bs, notes=["暫停營業，無目標日恢復證據"])
    notes = [] if bs == "OPERATIONAL" else ["營業狀態未提供"]
    offset = (target - today).days
    cur = place.get("currentOpeningHours")
    if 0 <= offset <= CURRENT_HOURS_MAX_OFFSET and isinstance(cur, dict) and "periods" in cur:
        periods = cur.get("periods")
        if isinstance(periods, list):
            iv = _intervals_from_current(periods, target)
            if iv is not None:
                return OpeningInfo("known", _merge(iv), bs, notes)
        notes.append("currentOpeningHours 結構無法解析")
    reg = place.get("regularOpeningHours")
    if isinstance(reg, dict) and isinstance(reg.get("periods"), list):
        iv = _intervals_from_regular(reg["periods"], target)
        if iv is not None:
            why = "超出特殊營業時間範圍（今天起 7 天內）" if offset > CURRENT_HOURS_MAX_OFFSET else "缺特殊營業時間"
            return OpeningInfo("provisional", _merge(iv), bs, notes + [f"{why}，以一般營業時間暫定"])
    return OpeningInfo("unknown", [], bs, notes + ["無營業時間資料"])
