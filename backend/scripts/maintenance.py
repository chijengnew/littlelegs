"""定期清理：限流計數（窗口結束後 24 小時內）、到期的冪等操作紀錄、超過保存期限的回饋。

冪等操作紀錄：query_operations、favorite_operations、check_in_operations。

操作紀錄只在 now ≥ expires_at 後清除；不清除未到期者。
用法：python -m scripts.maintenance
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import delete

from app.db.base import rowcount
from app.db.models import CheckInOperation, FavoriteOperation, QueryOperation
from app.ratelimit import purge_expired
from app.services import feedback

from ._common import db, setup_logging


async def run() -> dict:
    _, eng, factory = db()
    now = datetime.now(UTC)
    try:
        counters = await purge_expired(factory, now)
        async with factory() as s, s.begin():
            q = await s.execute(delete(QueryOperation).where(QueryOperation.expires_at <= now))
            f = await s.execute(delete(FavoriteOperation).where(FavoriteOperation.expires_at <= now))
            ci = await s.execute(delete(CheckInOperation).where(CheckInOperation.expires_at <= now))
        return {
            "rate_counters": counters,
            "query_operations": rowcount(q),
            "favorite_operations": rowcount(f),
            "check_in_operations": rowcount(ci),
            "feedback": await feedback.purge_expired(factory, now),
        }
    finally:
        await eng.dispose()


if __name__ == "__main__":
    setup_logging()
    print(asyncio.run(run()))
