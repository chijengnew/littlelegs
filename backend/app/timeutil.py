"""時間工具：Asia/Taipei 當地日期與 15 分鐘刻度；支援時間注入（clock injection）。"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TPE = ZoneInfo("Asia/Taipei")
GOOGLE_BILLING_TZ = ZoneInfo("America/Los_Angeles")
TICK = timedelta(minutes=15)

Clock = Callable[[], datetime]


def system_clock() -> datetime:
    return datetime.now(UTC)


def local_today(now: datetime) -> date:
    return now.astimezone(TPE).date()


def local_dt(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=TPE)


def parse_hhmm(s: str) -> time:
    if not isinstance(s, str) or len(s) != 5 or s[2] != ":":
        raise ValueError("時間格式須為 HH:MM")
    h, m = int(s[:2]), int(s[3:])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("時間超出範圍")
    return time(h, m)


def on_tick(t: time) -> bool:
    return t.minute % 15 == 0 and t.second == 0


def ceil_minute(dt: datetime) -> datetime:
    """往上取到整分鐘：行程時間顯示到分，車程秒數不向下取整。"""
    ts = dt.timestamp()
    step = 60
    return datetime.fromtimestamp(math.ceil(ts / step - 1e-9) * step, tz=dt.tzinfo or UTC)


def taipei_day_window_start_utc(now: datetime) -> datetime:
    """每日額度窗口起點：台北當地零點換算的 UTC 時間（前一日 16:00 UTC）。"""
    d = local_today(now)
    return local_dt(d, time(0, 0)).astimezone(UTC)


def billing_month_window_utc(now: datetime) -> tuple[datetime, datetime]:
    """Google 帳單月份窗口（美西時間當月 1 日零點至次月 1 日零點，換算為 UTC；自動處理日光節約）。"""
    local = now.astimezone(GOOGLE_BILLING_TZ)
    start = datetime(local.year, local.month, 1, tzinfo=GOOGLE_BILLING_TZ)
    nxt = datetime(local.year + (local.month == 12), local.month % 12 + 1, 1, tzinfo=GOOGLE_BILLING_TZ)
    return start.astimezone(UTC), nxt.astimezone(UTC)


def minute_window_start_utc(now: datetime) -> datetime:
    n = now.astimezone(UTC)
    return n.replace(second=0, microsecond=0)
