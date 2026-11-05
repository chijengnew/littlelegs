"""需要伺服器時鐘的驗證。"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from app.domain.schemas import Conditions
from app.errors import ApiError
from app.ids import uuid7_time
from app.timeutil import local_dt, local_today

NEW_SEARCH_DAYS = 30
KEY_MAX_AHEAD = timedelta(hours=24)
FAVORITE_KEY_WINDOW = timedelta(days=7)


def departure(c: Conditions) -> datetime:
    return local_dt(c.date, c.t_depart)


def check_new_search_date(c: Conditions, now: datetime) -> None:
    today = local_today(now)
    off = (c.date - today).days
    if off < 0 or off >= NEW_SEARCH_DAYS:
        raise ApiError(
            422,
            "DATE_OUT_OF_RANGE",
            "出遊日期須在今天起 30 天內（含今天）",
            errors=[{"loc": ["conditions", "date"], "msg": "出遊日期須在今天起 30 天內"}],
        )


def check_departure_future(c: Conditions, now: datetime) -> None:
    if departure(c) <= now:
        raise ApiError(409, "DEPARTURE_PASSED", "出發時間已過，請選擇新的時間")


def check_key_time(key: uuid.UUID, now: datetime) -> datetime:
    kt = uuid7_time(key)
    if kt > now + KEY_MAX_AHEAD:
        raise ApiError(409, "KEY_TIME_INVALID", "操作識別碼時間超前過多")
    return kt


def query_window_end(query_id: uuid.UUID, c: Conditions) -> datetime:
    """expires_at = max(key_time + 7 天, 出發時間點)，首次建立時計算並固定。"""
    return max(uuid7_time(query_id) + timedelta(days=7), departure(c))


def favorite_key_expiry(key: uuid.UUID) -> datetime:
    return uuid7_time(key) + FAVORITE_KEY_WINDOW
