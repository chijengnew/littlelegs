"""維運腳本共用：以操作者 IAM／OS 身分執行，沒有瀏覽器 App Check；外部呼叫同樣先扣應用出站額度。"""

from __future__ import annotations

import logging
import sys

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.db.session import build_engine
from app.external.google import HttpGoogleGateway
from app.logs import quiet_http_client_logs
from app.ratelimit import Limiter
from app.timeutil import system_clock


def setup_logging() -> None:
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
    )
    quiet_http_client_logs()


def db(settings: Settings | None = None) -> tuple[Settings, AsyncEngine, async_sessionmaker[AsyncSession]]:
    s = settings or get_settings()
    if not s.database_url:
        raise SystemExit("DATABASE_URL 未設定")
    eng = build_engine(s)
    return s, eng, async_sessionmaker(eng, expire_on_commit=False)


def google(settings: Settings, factory) -> HttpGoogleGateway:
    if not settings.google_server_api_key:
        raise SystemExit("GOOGLE_SERVER_API_KEY 未設定")
    lim = settings.limits
    return HttpGoogleGateway(
        settings.google_server_api_key,
        Limiter(factory, lim, system_clock),
        lim.worker_external_concurrency,
        lim.attempt_timeout_s,
    )
