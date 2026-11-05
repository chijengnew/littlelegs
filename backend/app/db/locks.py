"""跨 worker 協調鎖：同一 Firebase UID 的會員建立與刪帳。

- 使用專用連線的 MySQL GET_LOCK；GET_LOCK 是連線級鎖，COMMIT／ROLLBACK 不會釋放。
- 名稱採 UID 的 SHA-256 前綴，長度 ≤ 64；同一連線只取一次；有限等待。
- finally 一定 RELEASE_LOCK，確認回傳 1 才歸還連線池；狀態不明則 invalidate 連線（不歸還）。
- 不借用額度交易的連線，也不跨請求共用連線。
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.errors import ApiError


def lock_name(uid: str) -> str:
    return "ll:uid:" + hashlib.sha256(uid.encode("utf-8")).hexdigest()[:48]


@asynccontextmanager
async def uid_lock(engine: AsyncEngine, uid: str, wait_s: int = 5) -> AsyncIterator[None]:
    name = lock_name(uid)
    conn = await engine.connect()
    acquired = False
    state_known = False
    try:
        got = await conn.scalar(text("SELECT GET_LOCK(:n, :t)"), {"n": name, "t": wait_s})
        await conn.commit()
        state_known = True
        if got != 1:
            raise ApiError(503, "ACCOUNT_BUSY", "帳號操作進行中，請稍後再試")
        acquired = True
        yield
    finally:
        released_ok = state_known and not acquired
        pending: BaseException | None = None
        if acquired:
            try:
                r = await conn.scalar(text("SELECT RELEASE_LOCK(:n)"), {"n": name})
                await conn.commit()
                released_ok = r == 1
            except BaseException as e:
                released_ok = False
                pending = e
        if released_ok:
            await conn.close()
        else:
            await asyncio.shield(_discard(conn))
        if pending is not None:
            raise pending


async def _discard(conn) -> None:
    try:
        await conn.invalidate()
    finally:
        await conn.close()
