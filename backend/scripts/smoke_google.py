"""Google API 連線檢查：對每個用到的 Google 服務各送一次最小請求，確認金鑰、API 啟用與 IP 限制都正確。

五項全部執行且沒有重試時，共送出 5 次 HTTP 請求：每日 Google 外部請求額度扣 4 次、自動完成額度扣 1 次，
車程矩陣另計 4 個元素（2×2）；每月上限也依各計費項目分別計入。略過的項目不送出請求；暫時性失敗的重試另計。

檢查項目：
  1. Places Autocomplete（自動完成）
  2. Places Place Details：起訖點座標（id、location）
  3. Places Place Details：營業時間（取資料庫中一個已配對 Place ID 的景點）
  4. Routes Compute Route Matrix（2×2 車程矩陣）
  5. Weather 每日預報
  （Places Text Search 已由 place_ids 配對腳本使用，不重複檢查）

只印出每項結果與簡短摘要；不保存任何 Google 回應。
✓ 成功、－ 略過（前置條件不足，未實際送出請求，不算成功）、✗ 失敗；五項都是 ✓ 才算通過（結束碼 0）。
用法：python -m scripts.smoke_google
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import select

from app.db.models import Place
from app.external.google import Deadline, GoogleError
from app.ratelimit import QuotaExceeded

from ._common import db, google, setup_logging

TAIPEI_MAIN_STATION = (25.0478, 121.5170)
TAIPEI_101 = (25.0340, 121.5645)


SKIPPED = "略過"


async def _step(name: str, fn: Callable[[], Awaitable[str]]) -> str:
    """回傳 ok／skip／fail。"""
    try:
        summary = await fn()
    except QuotaExceeded as e:
        print(f"✗ {name}：額度已用完（{e.key}，上限 {e.limit}）")
        return "fail"
    except GoogleError as e:
        hint = {
            "denied": "金鑰被拒：確認此 API 已啟用、金鑰的 API 限制有勾選、IP 限制包含目前的對外 IP",
            "invalid_request": "請求格式被拒",
            "unavailable": "暫時無法連線，稍後再試",
            "not_found": "找不到此地點",
        }.get(e.kind, e.kind)
        print(f"✗ {name}：{hint}")
        return "fail"
    if summary.startswith(SKIPPED):
        print(f"－ {name}：{summary}")
        return "skip"
    print(f"✓ {name}：{summary}")
    return "ok"


async def main() -> int:
    settings, eng, factory = db()
    g = google(settings, factory)
    results: list[str] = []
    try:
        token = str(uuid.uuid4())
        picked: dict[str, str] = {}

        async def autocomplete() -> str:
            sugg = await g.autocomplete("台北車站", token, Deadline(10))
            if not sugg:
                raise GoogleError("invalid_response", "沒有建議")
            picked["id"] = sugg[0]["google_place_id"]
            return f"取得 {len(sugg)} 筆建議"

        async def resolve() -> str:
            if "id" not in picked:
                return f"{SKIPPED}（自動完成未成功，無建議可解析）"
            lat, lon = await g.place_location(picked["id"], Deadline(10), session_token=token)
            return f"取得座標（{lat:.4f}, {lon:.4f}）"

        async def hours() -> str:
            async with factory() as s:
                p = (
                    await s.execute(
                        select(Place)
                        .where(Place.place_id_status == "accepted", Place.google_place_id.is_not(None))
                        .limit(1)
                    )
                ).scalar()
            if p is None or p.google_place_id is None:
                return f"{SKIPPED}（資料庫中還沒有已配對 Place ID 的景點）"
            raw = await g.place_hours(p.google_place_id, Deadline(10))
            has = "有" if raw.get("regularOpeningHours") or raw.get("currentOpeningHours") else "無"
            return f"{p.name}：營業狀態 {raw.get('businessStatus') or '未提供'}，{has}營業時間資料"

        async def matrix() -> str:
            m = await g.route_matrix([TAIPEI_MAIN_STATION, TAIPEI_101], Deadline(15))
            el = m.get((0, 1))
            if el is None or el.status != "ok" or el.seconds is None:
                raise GoogleError("invalid_response", "缺少車程")
            return f"台北車站 → 台北 101 開車約 {round(el.seconds / 60)} 分鐘"

        async def weather() -> str:
            days = await g.daily_forecast(*TAIPEI_MAIN_STATION, 1, 10, Deadline(10))
            if not days:
                raise GoogleError("invalid_response", "沒有預報")
            return f"取得 {len(days)} 天預報"

        results.append(await _step("Places 自動完成", autocomplete))
        results.append(await _step("Places 起訖點座標", resolve))
        results.append(await _step("Places 營業時間", hours))
        results.append(await _step("Routes 車程矩陣", matrix))
        results.append(await _step("Weather 天氣預報", weather))
    finally:
        await g.aclose()
        await eng.dispose()
    ok, skip, fail = (results.count(x) for x in ("ok", "skip", "fail"))
    print(f"\n成功 {ok}、略過 {skip}、失敗 {fail}（共 {len(results)} 項）")
    if ok == len(results):
        print("全部通過")
        return 0
    if fail == 0:
        print("未全部檢查：略過的項目沒有實際送出請求，補齊前置條件後再執行一次")
    return 1


if __name__ == "__main__":
    setup_logging()
    sys.exit(asyncio.run(main()))
