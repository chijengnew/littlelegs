"""MySQL 固定時間窗限流與出站額度准入。

- 以 (counter_key, window_start) 為主鍵；每個計數依該維度的實際增量 delta 原子准入：
  INSERT ... VALUES(:delta) ON DUPLICATE KEY UPDATE count = count + :delta，
  同一交易讀回目前計數判斷；任一超限即回滾整筆並拒絕。不把 affected rows 當計數。
- 依固定順序（counter_key 排序）處理以降低 deadlock；1213／1205 回滾後有限次重試。
- 使用獨立短交易 session，提交並釋放連線後才呼叫外部 API；不在持鎖時等待外部 API。
- 每次外部嘗試（含重試）都要先取得額度；已送出的請求不退款。
- 每日窗口以 Asia/Taipei 零點換算為 UTC；計數列在窗口結束後 24 小時內可清除。
- 每月窗口對齊 Google 帳單月份（美西時間每月 1 日零點重置），依計費項目（SKU）分別計數，
  上限預設等於該項目的每月免費額度；計的是嘗試次數（含失敗），比 Google 實際計費保守。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.base import rowcount
from app.db.models import RateCounter
from app.errors import ApiError
from app.timeutil import billing_month_window_utc, minute_window_start_utc, taipei_day_window_start_utc

RETRYABLE_MYSQL = {1213, 1205}
MAX_TX_RETRIES = 3


@dataclass(frozen=True)
class Counter:
    key: str
    window: str
    limit: int
    delta: int = 1


class QuotaExceeded(Exception):
    def __init__(self, key: str, limit: int, window: str) -> None:
        super().__init__(key)
        self.key, self.limit, self.window = key, limit, window


SKU_PLACE_DETAILS_ESSENTIALS = "place_details_essentials"
SKU_PLACE_DETAILS_ENTERPRISE = "place_details_enterprise"
SKU_AUTOCOMPLETE = "autocomplete"
SKU_MATRIX_ELEMENTS = "matrix_elements"
SKU_WEATHER = "weather"
SKU_TEXT_SEARCH_PRO = "text_search_pro"
SKU_FREE = "free"

_SKU_LIMIT_FIELD = {
    SKU_PLACE_DETAILS_ESSENTIALS: "monthly_place_details_essentials",
    SKU_PLACE_DETAILS_ENTERPRISE: "monthly_place_details_enterprise",
    SKU_AUTOCOMPLETE: "monthly_autocomplete",
    SKU_MATRIX_ELEMENTS: "monthly_matrix_elements",
    SKU_WEATHER: "monthly_weather",
    SKU_TEXT_SEARCH_PRO: "monthly_text_search_pro",
}


def quota_api_error(e: QuotaExceeded) -> ApiError:
    """出站額度耗盡（每日／每月額度或自動完成 session 上限）→ 429 problem+json。"""
    if e.window == "billing_month":
        return ApiError(
            429,
            "MONTHLY_QUOTA_EXHAUSTED",
            "本月外部服務免費額度已用完，下個月恢復",
            extra={"limit_window": "billing_month"},
        )
    if e.window == "session":
        return ApiError(
            429,
            "AUTOCOMPLETE_SESSION_LIMIT",
            "此次地點搜尋已達上限，請從建議中選定或重新開始",
            extra={"limit_window": "session"},
        )
    return ApiError(
        429,
        "QUOTA_EXHAUSTED",
        "今日外部服務額度已用完或達上限",
        headers={"Retry-After": "3600"},
        extra={"limit_window": e.window},
    )


def _window(c: Counter, now: datetime) -> tuple[datetime, datetime]:
    if c.window == "minute":
        start = minute_window_start_utc(now)
        return start, start + timedelta(minutes=1)
    if c.window == "day":
        start = taipei_day_window_start_utc(now)
        return start, start + timedelta(days=1)
    if c.window == "session":
        start = taipei_day_window_start_utc(now)
        return start, start + timedelta(days=1)
    if c.window == "billing_month":
        return billing_month_window_utc(now)
    raise ValueError(c.window)


def _mysql_errno(e: OperationalError) -> int | None:
    orig = getattr(e, "orig", None)
    args = getattr(orig, "args", ())
    return args[0] if args and isinstance(args[0], int) else None


async def admit(factory: async_sessionmaker[AsyncSession], counters: list[Counter], now: datetime) -> None:
    """全部計數通過才提交；任一超限 → QuotaExceeded（整筆回滾，不計入）。"""
    ordered = sorted(counters, key=lambda c: c.key)
    for attempt in range(MAX_TX_RETRIES):
        try:
            async with factory() as s, s.begin():
                for c in ordered:
                    ws, we = _window(c, now)
                    stmt = mysql_insert(RateCounter).values(
                        counter_key=c.key, window_start=ws, count=c.delta, purge_after=we + timedelta(hours=24)
                    )
                    await s.execute(stmt.on_duplicate_key_update(count=RateCounter.count + c.delta))
                    cur = (
                        await s.execute(
                            select(RateCounter.count).where(
                                RateCounter.counter_key == c.key, RateCounter.window_start == ws
                            )
                        )
                    ).scalar_one()
                    if cur > c.limit:
                        raise QuotaExceeded(c.key, c.limit, c.window)
            return
        except OperationalError as e:
            if _mysql_errno(e) in RETRYABLE_MYSQL and attempt < MAX_TX_RETRIES - 1:
                await asyncio.sleep(0.02 * (attempt + 1))
                continue
            raise


async def purge_expired(factory: async_sessionmaker[AsyncSession], now: datetime) -> int:
    async with factory() as s, s.begin():
        r = await s.execute(delete(RateCounter).where(RateCounter.purge_after <= now))
        return rowcount(r)


async def delete_uid_counters(s: AsyncSession, uid: str) -> None:
    """刪帳時清除會員 UID 限流列（在刪帳交易內呼叫）。"""
    await s.execute(delete(RateCounter).where(RateCounter.counter_key.like(f"uid:{_escape_like(uid)}:%")))


def _escape_like(v: str) -> str:
    return v.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


class Limiter:
    """入站（使用者請求）與出站（外部 API 呼叫）計數分開。"""

    def __init__(self, factory: async_sessionmaker[AsyncSession], limits, clock) -> None:
        self.factory, self.lim, self.clock = factory, limits, clock

    async def inbound(self, category: str, ip: str, uid: str | None) -> None:
        cs = [Counter(f"ip:{ip}:all", "minute", self.lim.ip_all_per_min)]
        if category == "paid":
            if uid:
                cs.append(Counter(f"uid:{uid}:paid", "minute", self.lim.uid_member_paid_per_min))
            else:
                cs.append(Counter(f"ip:{ip}:guest_paid", "minute", self.lim.ip_guest_paid_per_min))
        elif category == "endpoint_select":
            cs.append(Counter(f"ip:{ip}:select", "minute", self.lim.ip_endpoint_select_per_min))
        elif category == "feedback":
            cs.append(Counter(f"ip:{ip}:feedback", "minute", self.lim.ip_feedback_per_min))
        await admit(self.factory, cs, self.clock())

    async def outbound(
        self,
        *,
        google_requests: int = 0,
        autocomplete: int = 0,
        matrix_elements: int = 0,
        photos: int = 0,
        autocomplete_session: str | None = None,
        sku: str | None = None,
        sku_units: int = 1,
    ) -> None:
        """sku：本次外部請求的 Google 計費項目；sku_units：計費單位數（矩陣為元素數，其餘為 1）。"""
        cs = []
        if google_requests:
            cs.append(Counter("g:google_requests", "day", self.lim.daily_google_requests, google_requests))
        if autocomplete:
            cs.append(Counter("g:autocomplete", "day", self.lim.daily_autocomplete, autocomplete))
        if matrix_elements:
            cs.append(Counter("g:matrix_elements", "day", self.lim.daily_matrix_elements, matrix_elements))
        if photos:
            cs.append(Counter("g:photos", "day", self.lim.daily_photos, photos))
        if autocomplete_session:
            cs.append(Counter(f"as:{autocomplete_session}", "session", self.lim.autocomplete_per_session, 1))
        if sku is not None and sku != SKU_FREE:
            limit = getattr(self.lim, _SKU_LIMIT_FIELD[sku])
            cs.append(Counter(f"gm:{sku}", "billing_month", limit, sku_units))
        if cs:
            await admit(self.factory, cs, self.clock())
