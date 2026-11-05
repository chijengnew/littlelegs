"""FastAPI 應用入口。

- create_app() 不需要真實機密或資料庫連線即可建立（CI 以 app.openapi() 匯出契約）；
  機密與連線在 lifespan 才載入。
- 正式環境停用 App Check、設定 Auth Emulator、萬用 CORS 或未設 RDS CA 時拒絕啟動。
- CORS 精確列出允許來源、方法與實際使用的標頭；OPTIONS 預檢不要求 Auth／App Check。
- 日誌不記錄 Token、金鑰、孩子資料、精確位置或請求 body。
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import errors
from app.api.problems import use_problem_media_type
from app.api.v1 import router as v1_router
from app.config import Settings, assert_safe_for_environment, get_settings
from app.logs import quiet_http_client_logs
from app.state import AppState

log = logging.getLogger("littlelegs")

CORS_HEADERS = ["Authorization", "X-Firebase-AppCheck", "Idempotency-Key", "Content-Type"]
CORS_METHODS = ["GET", "POST", "DELETE"]


def _init_sentry(settings: Settings) -> None:
    import os

    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return
    import sentry_sdk

    def scrub(event, _hint):
        req = event.get("request") or {}
        for k in ("data", "query_string", "cookies"):
            req.pop(k, None)
        hdrs = req.get("headers") or {}
        for h in list(hdrs):
            if h.lower() in ("authorization", "x-firebase-appcheck", "cookie"):
                hdrs[h] = "[Filtered]"
        for ex in (event.get("exception") or {}).get("values", []):
            for fr in (ex.get("stacktrace") or {}).get("frames", []):
                fr.pop("vars", None)
        event.pop("breadcrumbs", None)
        return event

    sentry_sdk.init(
        dsn=dsn,
        environment=settings.env,
        send_default_pii=False,
        traces_sample_rate=0.0,
        profiles_sample_rate=0.0,
        include_local_variables=False,
        max_breadcrumbs=0,
        before_send=scrub,
    )


def default_state_factory(settings: Settings) -> AppState:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.session import build_engine
    from app.external.google import HttpGoogleGateway
    from app.ratelimit import Limiter
    from app.security.firebase import FirebaseVerifier
    from app.services.intents import IntentStore, LocalIntentStore, S3IntentStore
    from app.timeutil import system_clock

    engine = build_engine(settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    limiter = Limiter(factory, settings.limits, system_clock)
    google = None
    if settings.google_server_api_key:
        lim = settings.limits
        google = HttpGoogleGateway(
            settings.google_server_api_key, limiter, lim.worker_external_concurrency, lim.attempt_timeout_s
        )
    intents: IntentStore
    if settings.deletion_intent_backend == "s3":
        if not settings.deletion_intent_bucket:
            raise RuntimeError("DELETION_INTENT_BUCKET 未設定")
        intents = S3IntentStore(settings.deletion_intent_bucket, settings.deletion_intent_prefix)
    else:
        intents = LocalIntentStore(settings.deletion_intent_local_dir)
    return AppState(
        settings,
        system_clock,
        engine,
        factory,
        limiter,
        google,
        FirebaseVerifier(settings.firebase_project_id),
        intents,
    )


def create_app(
    settings: Settings | None = None, state_factory: Callable[[Settings], AppState] | None = None
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        assert_safe_for_environment(settings)
        _init_sentry(settings)
        from app.domain import solver_runner

        solver_runner.configure(settings.limits.algorithm_concurrency)
        st = (state_factory or default_state_factory)(settings)
        app.state.ll = st
        try:
            yield
        finally:
            if st.google is not None and hasattr(st.google, "aclose"):
                await st.google.aclose()
            await st.engine.dispose()

    app = FastAPI(
        title="Littlelegs API",
        version="0.1.0",
        lifespan=lifespan,
        description="Littlelegs 親子出遊規劃 API。所有功能路徑以 `/v1` 開頭；發生錯誤時回傳統一格式的錯誤說明。",
    )
    errors.install(app)
    use_problem_media_type(app)

    @app.middleware("http")
    async def trace(request: Request, call_next):
        request.state.trace_id = str(uuid.uuid4())
        resp = await call_next(request)
        resp.headers["X-Trace-Id"] = request.state.trace_id
        resp.headers["Cache-Control"] = "no-store"
        return resp

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=CORS_METHODS,
            allow_headers=CORS_HEADERS,
            expose_headers=["Retry-After", "X-Trace-Id"],
            allow_credentials=False,
            max_age=600,
        )

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict:
        return {"status": "ok"}

    app.include_router(v1_router)
    return app


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
    )
    quiet_http_client_logs()


_configure_logging()
app = create_app()
