"""應用執行期依賴容器（lifespan 建立；測試可替換 clock、Google gateway、驗證器與意圖儲存）。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Settings
from app.external.google import GoogleGateway
from app.ratelimit import Limiter
from app.security.firebase import Verifier
from app.services.intents import IntentStore
from app.timeutil import Clock


@dataclass
class AppState:
    settings: Settings
    clock: Clock
    engine: AsyncEngine
    factory: async_sessionmaker[AsyncSession]
    limiter: Limiter
    google: GoogleGateway | None
    verifier: Verifier
    intents: IntentStore
