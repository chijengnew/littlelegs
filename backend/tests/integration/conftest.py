"""MySQL 整合測試（與 RDS 相同主要版本；不用 SQLite）。

需要：TEST_DATABASE_URL（應用帳號，無 DDL）與 TEST_MIGRATION_DATABASE_URL（migration 帳號）。
外部服務一律以 fake 取代（Firebase Auth／App Check、Google），不產生費用；FakeGoogle 仍走應用出站額度准入。
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from asgi_lifespan import LifespanManager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Limits, Settings
from app.db.models import Dataset, ImportBatch, Place, PlaceFacility, PlaceType, SourceRecord
from app.errors import ApiError
from app.external.google import GoogleError, MatrixElement
from app.ids import new_id
from app.ratelimit import (
    SKU_AUTOCOMPLETE,
    SKU_FREE,
    SKU_MATRIX_ELEMENTS,
    SKU_PLACE_DETAILS_ENTERPRISE,
    SKU_PLACE_DETAILS_ESSENTIALS,
    SKU_TEXT_SEARCH_PRO,
    SKU_WEATHER,
    Limiter,
)
from app.security.firebase import AccountInfo, AuthClaims
from app.services.intents import LocalIntentStore
from app.state import AppState

DB_URL = os.environ.get("TEST_DATABASE_URL")
MIG_URL = os.environ.get("TEST_MIGRATION_DATABASE_URL")
pytestmark = pytest.mark.integration
BACKEND = Path(__file__).resolve().parents[2]

NOW = datetime(2026, 10, 20, 1, 0, tzinfo=UTC)

if not DB_URL or not MIG_URL:
    pytest.skip("未設定 TEST_DATABASE_URL／TEST_MIGRATION_DATABASE_URL", allow_module_level=True)


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class FakeVerifier:
    """Token 格式：tok:<uid>[:<auth_time>]。revoked／deleted 模擬撤銷與已刪除帳號；
    uid 以 unverified 開頭者模擬 Email 尚未驗證；verified_later 模擬 Token 簽發後才完成驗證。
    accounts 為 Admin 端看得到的帳號（uid → 建立時間毫秒）；未列入者建立時間不明。"""

    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.revoked: set[str] = set()
        self.deleted: set[str] = set()
        self.verified_later: set[str] = set()
        self.accounts: dict[str, int | None] = {}
        self.app_check_calls = 0

    async def verify_id_token(self, token: str, check_revoked: bool) -> AuthClaims:
        parts = token.split(":")
        if len(parts) < 2 or parts[0] != "tok":
            raise ApiError(401, "AUTH_TOKEN_INVALID", "登入憑證無效")
        uid = parts[1]
        if check_revoked and (uid in self.revoked or uid in self.deleted):
            raise ApiError(401, "AUTH_REAUTH_REQUIRED", "需要重新登入")
        at = int(parts[2]) if len(parts) > 2 else int(self.clock().timestamp()) - 3600
        return AuthClaims(uid, at, "password", email_verified=not uid.startswith("unverified"))

    async def verify_app_check(self, token: str) -> None:
        self.app_check_calls += 1
        if token != "ok":
            raise ApiError(403, "APP_CHECK_FAILED", "App Check 驗證失敗")

    async def delete_user(self, uid: str) -> None:
        self.deleted.add(uid)

    async def get_account(self, uid: str) -> AccountInfo | None:
        if uid in self.deleted:
            return None
        verified = not uid.startswith("unverified") or uid in self.verified_later
        return AccountInfo(uid, verified, ("password",), self.accounts.get(uid))

    async def list_unverified_accounts(self) -> list[AccountInfo]:
        infos = [await self.get_account(uid) for uid in self.accounts]
        return [a for a in infos if a is not None and not a.email_verified]


class FakeGoogle:
    """回傳固定資料；每次呼叫依真實維度扣應用出站額度。不保存任何回應。"""

    def __init__(self, limiter: Limiter) -> None:
        self.lim = limiter
        self.calls: list[str] = []
        self.locations = {"ChIJhome": (25.0330, 121.5654)}
        self.hours: dict[str, dict] = {}
        self.forecast: list[dict] | None = None
        self.matrix_seconds = 900
        self.fail_matrix = False

    async def place_location(self, place_id, deadline, session_token=None):
        await self.lim.outbound(google_requests=1, sku=SKU_PLACE_DETAILS_ESSENTIALS)
        self.calls.append("place_location")
        if place_id not in self.locations:
            raise GoogleError("not_found")
        return self.locations[place_id]

    async def place_hours(self, place_id, deadline):
        await self.lim.outbound(google_requests=1, sku=SKU_PLACE_DETAILS_ENTERPRISE)
        self.calls.append("place_hours")
        if place_id in self.hours:
            return self.hours[place_id]
        return {
            "businessStatus": "OPERATIONAL",
            "regularOpeningHours": {
                "periods": [
                    {"open": {"day": d, "hour": 8, "minute": 0}, "close": {"day": d, "hour": 20, "minute": 0}}
                    for d in range(7)
                ]
            },
        }

    async def autocomplete(self, text, session_token, deadline):
        await self.lim.outbound(autocomplete=1, autocomplete_session=session_token, sku=SKU_AUTOCOMPLETE)
        self.calls.append("autocomplete")
        return [{"google_place_id": "ChIJhome", "text": "某處"}]

    async def route_matrix(self, points, deadline):
        n = len(points)
        await self.lim.outbound(google_requests=1, matrix_elements=n * n, sku=SKU_MATRIX_ELEMENTS, sku_units=n * n)
        self.calls.append(f"matrix:{n}")
        if self.fail_matrix:
            raise GoogleError("unavailable")
        return {
            (i, j): MatrixElement("ok", 0 if i == j else self.matrix_seconds, 1000, "ROUTE_EXISTS")
            for i in range(n)
            for j in range(n)
        }

    async def daily_forecast(self, lat, lon, days, page_size, deadline):
        await self.lim.outbound(google_requests=1, sku=SKU_WEATHER)
        self.calls.append("weather")
        return self.forecast

    async def text_search(self, query, lat, lon, deadline):
        await self.lim.outbound(google_requests=1, sku=SKU_TEXT_SEARCH_PRO)
        return []

    async def place_id_only(self, place_id, deadline):
        await self.lim.outbound(google_requests=1, sku=SKU_FREE)
        return place_id


@pytest.fixture(scope="session")
def migrated() -> None:
    import asyncio

    env = {**os.environ, "MIGRATION_DATABASE_URL": MIG_URL}

    async def drop_all():
        eng = create_async_engine(MIG_URL)
        async with eng.begin() as c:
            await c.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            rows = (await c.execute(text("SHOW TABLES"))).scalars().all()
            for t in rows:
                await c.execute(text(f"DROP TABLE `{t}`"))
            await c.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        await eng.dispose()

    asyncio.run(drop_all())
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr
    r = subprocess.run([sys.executable, "-m", "alembic", "check"], cwd=BACKEND, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


PLACES = {
    "museum": ("兒童探索博物館", 25.0400, 121.5600, "museum", "indoor", {"nursing_room": "yes"}),
    "park": ("森林親子公園", 25.0300, 121.5350, "park_playground", "outdoor", {"playground": "yes"}),
    "factory": ("糖果觀光工廠", 25.0600, 121.5800, "tourism_factory", "indoor", {}),
}


@pytest.fixture
async def seeded(migrated):
    eng = create_async_engine(DB_URL, connect_args={"init_command": "SET time_zone = '+00:00'"})
    f = async_sessionmaker(eng, expire_on_commit=False)
    async with eng.begin() as c:
        await c.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in (
            "favorite_aliases",
            "favorite_operations",
            "favorite_stops",
            "favorites",
            "history_stops",
            "histories",
            "query_operations",
            "private_endpoint_aliases",
            "private_endpoints",
            "users",
            "rate_counters",
            "place_types",
            "place_facilities",
            "place_age_ranges",
            "place_age_exclusions",
            "place_id_aliases",
            "feedback",
            "places",
            "source_records",
            "import_batches",
            "datasets",
        ):
            await c.execute(text(f"DELETE FROM `{t}`"))
        await c.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    ids: dict[str, uuid.UUID] = {}
    async with f() as s, s.begin():
        ds = Dataset(
            id=new_id(),
            dataset_key="test_ds",
            title="測試資料集",
            provider="測試",
            source_url="https://x",
            license="政府資料開放授權條款-第1版",
            license_status="verified",
            role="primary",
            import_policy="import",
        )
        s.add(ds)
        await s.flush()
        b = ImportBatch(id=new_id(), dataset_id=ds.id, mode="full", status="succeeded", started_at=NOW)
        s.add(b)
        await s.flush()
        for key, (name, la, lo, pt, indoor, facs) in [
            *PLACES.items(),
            ("hotel", ("親子旅店", 25.0335, 121.5650, None, None, {"crib": "yes"})),
        ]:
            pid = new_id()
            ids[key] = pid
            kind = "lodging" if key == "hotel" else "attraction"
            s.add(
                Place(
                    id=pid,
                    kind=kind,
                    name=name,
                    address=f"臺北市{name}路1號",
                    city="臺北市",
                    lat=Decimal(str(la)),
                    lon=Decimal(str(lo)),
                    primary_type=pt,
                    indoor=indoor,
                    indoor_confirmation="inferred" if indoor else "unknown",
                    google_place_id=None if kind == "lodging" else f"ChIJ{key}",
                    place_id_status="none" if kind == "lodging" else "accepted",
                )
            )
            await s.flush()
            rid = new_id()
            s.add(
                SourceRecord(
                    id=rid,
                    dataset_id=ds.id,
                    source_key=key,
                    place_id=pid,
                    first_batch_id=b.id,
                    last_seen_batch_id=b.id,
                    name=name,
                    lat=Decimal(str(la)),
                    lon=Decimal(str(lo)),
                )
            )
            await s.flush()
            p = await s.get(Place, pid)
            p.coord_source_record_id = rid
            if pt:
                s.add(
                    PlaceType(
                        place_id=pid,
                        type=pt,
                        confirmation="confirmed",
                        source_type="open_data",
                        evidence_record_id=rid,
                        evidence_note="test",
                    )
                )
            for fac, st_ in facs.items():
                s.add(
                    PlaceFacility(
                        place_id=pid,
                        facility=fac,
                        status=st_,
                        confirmation="confirmed",
                        source_type="open_data",
                        evidence_record_id=rid,
                        evidence_note="test",
                    )
                )
    yield ids
    await eng.dispose()


@pytest.fixture
async def env(seeded, tmp_path):
    from app.main import create_app

    clock = Clock(NOW)
    settings = Settings(
        env="test",
        database_url=DB_URL,
        app_check_enforce=False,
        deletion_intent_backend="local",
        deletion_intent_local_dir=str(tmp_path / "intents"),
        limits=Limits(),
    )
    holder: dict = {}

    def factory(s: Settings) -> AppState:
        eng = create_async_engine(
            DB_URL, pool_pre_ping=True, connect_args={"charset": "utf8mb4", "init_command": "SET time_zone = '+00:00'"}
        )
        fac = async_sessionmaker(eng, expire_on_commit=False)
        lim = Limiter(fac, s.limits, clock)
        st = AppState(
            s, clock, eng, fac, lim, FakeGoogle(lim), FakeVerifier(clock), LocalIntentStore(s.deletion_intent_local_dir)
        )
        holder["st"] = st
        return st

    app = create_app(settings, factory)
    async with LifespanManager(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("10.0.0.1", 1234)), base_url="http://test"
        ) as client:
            yield {"client": client, "st": holder["st"], "ids": seeded, "clock": clock}
