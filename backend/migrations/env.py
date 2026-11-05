"""Alembic 非同步 migration 環境。

正式環境：
- migration 由獨立操作者身分執行，帳號採 RDS IAM 資料庫驗證；token 以操作者自身 IAM 憑證產生，
  經環境變數 MIGRATION_DB_PASSWORD 只傳給本次程序，不寫入磁碟或 shell 歷史。
- IAM 驗證要求 TLS：設定 MIGRATION_DB_SSL_CA 指向 RDS CA bundle，驗證主機名稱。
- 不從 EC2 instance profile 取得 migration 憑證。
"""

from __future__ import annotations

import asyncio
import os
import ssl
from logging.config import fileConfig
from urllib.parse import quote_plus

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    url = os.environ.get("MIGRATION_DATABASE_URL")
    if not url:
        raise RuntimeError("請設定 MIGRATION_DATABASE_URL（例如 mysql+aiomysql://migrator@<rds-endpoint>:3306/littlelegs）")
    pw = os.environ.get("MIGRATION_DB_PASSWORD")
    if pw and "@" in url and ":" not in url.split("//", 1)[1].split("@", 1)[0]:
        scheme, rest = url.split("//", 1)
        user, host = rest.split("@", 1)
        url = f"{scheme}//{user}:{quote_plus(pw)}@{host}"
    return url


def _connect_args() -> dict:
    args: dict = {"charset": "utf8mb4", "init_command": "SET time_zone = '+00:00'"}
    ca = os.environ.get("MIGRATION_DB_SSL_CA")
    if ca:
        ctx = ssl.create_default_context(cafile=ca)
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        args["ssl"] = ctx
    return args


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(_url(), poolclass=pool.NullPool, connect_args=_connect_args())
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
