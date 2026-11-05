"""AsyncEngine 與 session factory（SQLAlchemy 2.0 async + aiomysql）。

- engine／factory 在同一 worker、同一事件迴圈的應用生命週期中共用；lifespan 關閉時 dispose。
- AsyncSession 不跨 task 共用；出站額度准入使用獨立短交易 session（見 app.ratelimit）。
- 連線：utf8mb4、time_zone=+00:00、pool_pre_ping、pool_recycle < wait_timeout、TLS 驗證 RDS CA 與主機名稱。
"""

from __future__ import annotations

import ssl
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings

_engine: AsyncEngine | None = None
_factory: async_sessionmaker[AsyncSession] | None = None


def connect_args(ssl_ca: str | None) -> dict:
    """aiomysql 連線參數；提供 CA bundle 時強制 TLS 並驗證 CA 與主機名稱（應用與匯入腳本共用）。"""
    args: dict = {"charset": "utf8mb4", "init_command": "SET time_zone = '+00:00'"}
    if ssl_ca:
        ctx = ssl.create_default_context(cafile=ssl_ca)
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        args["ssl"] = ctx
    return args


def build_engine(s: Settings) -> AsyncEngine:
    return create_async_engine(
        s.database_url,
        pool_pre_ping=True,
        pool_recycle=s.db_pool_recycle_s,
        connect_args=connect_args(s.db_ssl_ca),
        hide_parameters=True,
    )


def init_engine(s: Settings) -> None:
    global _engine, _factory
    _engine = build_engine(s)
    _factory = async_sessionmaker(_engine, expire_on_commit=False)


async def dispose_engine() -> None:
    global _engine, _factory
    if _engine is not None:
        await _engine.dispose()
    _engine, _factory = None, None


def engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("資料庫尚未初始化")
    return _engine


def session_factory() -> async_sessionmaker[AsyncSession]:
    if _factory is None:
        raise RuntimeError("資料庫尚未初始化")
    return _factory


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory()() as s:
        yield s
