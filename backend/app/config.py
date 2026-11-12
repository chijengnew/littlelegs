"""設定：只從環境變數讀取；機密在 lifespan 或首次使用時才取得（讓 CI 能在無機密下匯出 OpenAPI）。

正式環境機密來自 Parameter Store SecureString（由部署流程注入或啟動時讀取），不寫入程式碼。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    v = os.environ.get(name)
    return default if v is None or not v.strip() else int(v)


def _float(name: str, default: float) -> float:
    v = os.environ.get(name)
    return default if v is None or not v.strip() else float(v)


@dataclass(frozen=True)
class Stamping:
    """定位核對門檻（初始測試值，依試點實測再調整；不是防作弊保證）。"""

    max_accuracy_m: float = 100.0
    max_distance_m: float = 150.0


@dataclass(frozen=True)
class Limits:
    """初始應用限額（專案初值，非 Google 官方配額或費用保證）。"""

    ip_all_per_min: int = 30
    ip_guest_paid_per_min: int = 5
    uid_member_paid_per_min: int = 10
    ip_endpoint_select_per_min: int = 20
    ip_feedback_per_min: int = 3
    uid_stamp_per_min: int = 10
    daily_google_requests: int = 1000
    daily_autocomplete: int = 500
    daily_matrix_elements: int = 2500
    daily_photos: int = 100
    monthly_place_details_essentials: int = 10000
    monthly_place_details_enterprise: int = 1000
    monthly_autocomplete: int = 10000
    monthly_matrix_elements: int = 10000
    monthly_weather: int = 10000
    monthly_text_search_pro: int = 5000
    autocomplete_per_session: int = 10
    worker_external_concurrency: int = 4
    attempt_timeout_s: float = 10.0
    request_deadline_s: float = 30.0
    algorithm_budget_s: float = 5.0
    algorithm_concurrency: int = 1


@dataclass(frozen=True)
class Settings:
    env: str = "development"
    database_url: str = field(default="", repr=False)
    db_ssl_ca: str | None = None
    db_pool_recycle_s: int = 1800
    cors_origins: tuple[str, ...] = ()
    app_check_enforce: bool = True
    google_server_api_key: str | None = field(default=None, repr=False)
    firebase_project_id: str | None = None
    deletion_intent_backend: str = "s3"
    deletion_intent_bucket: str | None = None
    deletion_intent_prefix: str = "littlelegs/deletion-intents/"
    deletion_intent_local_dir: str = "/tmp/littlelegs-intents"
    limits: Limits = field(default_factory=Limits)
    stamping: Stamping = field(default_factory=Stamping)

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    lim = Limits(
        ip_all_per_min=_int("LIMIT_IP_ALL_PER_MIN", 30),
        ip_guest_paid_per_min=_int("LIMIT_IP_GUEST_PAID_PER_MIN", 5),
        uid_member_paid_per_min=_int("LIMIT_UID_MEMBER_PAID_PER_MIN", 10),
        ip_endpoint_select_per_min=_int("LIMIT_IP_ENDPOINT_SELECT_PER_MIN", 20),
        ip_feedback_per_min=_int("LIMIT_IP_FEEDBACK_PER_MIN", 3),
        uid_stamp_per_min=_int("LIMIT_UID_STAMP_PER_MIN", 10),
        daily_google_requests=_int("LIMIT_DAILY_GOOGLE_REQUESTS", 1000),
        daily_autocomplete=_int("LIMIT_DAILY_AUTOCOMPLETE", 500),
        daily_matrix_elements=_int("LIMIT_DAILY_MATRIX_ELEMENTS", 2500),
        daily_photos=_int("LIMIT_DAILY_PHOTOS", 100),
        monthly_place_details_essentials=_int("LIMIT_MONTHLY_PLACE_DETAILS_ESSENTIALS", 10000),
        monthly_place_details_enterprise=_int("LIMIT_MONTHLY_PLACE_DETAILS_ENTERPRISE", 1000),
        monthly_autocomplete=_int("LIMIT_MONTHLY_AUTOCOMPLETE", 10000),
        monthly_matrix_elements=_int("LIMIT_MONTHLY_MATRIX_ELEMENTS", 10000),
        monthly_weather=_int("LIMIT_MONTHLY_WEATHER", 10000),
        monthly_text_search_pro=_int("LIMIT_MONTHLY_TEXT_SEARCH_PRO", 5000),
    )
    origins = tuple(o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip())
    return Settings(
        env=os.environ.get("APP_ENV", "development"),
        database_url=os.environ.get("DATABASE_URL", ""),
        db_ssl_ca=os.environ.get("DB_SSL_CA") or None,
        db_pool_recycle_s=_int("DB_POOL_RECYCLE_S", 1800),
        cors_origins=origins,
        app_check_enforce=_bool("APP_CHECK_ENFORCE", True),
        google_server_api_key=os.environ.get("GOOGLE_SERVER_API_KEY") or None,
        firebase_project_id=os.environ.get("FIREBASE_PROJECT_ID") or None,
        deletion_intent_backend=os.environ.get("DELETION_INTENT_BACKEND", "s3"),
        deletion_intent_bucket=os.environ.get("DELETION_INTENT_BUCKET") or None,
        deletion_intent_prefix=os.environ.get("DELETION_INTENT_PREFIX", "littlelegs/deletion-intents/"),
        deletion_intent_local_dir=os.environ.get("DELETION_INTENT_LOCAL_DIR", "/tmp/littlelegs-intents"),
        limits=lim,
        stamping=Stamping(
            max_accuracy_m=_float("STAMP_MAX_ACCURACY_M", 100.0),
            max_distance_m=_float("STAMP_MAX_DISTANCE_M", 150.0),
        ),
    )


class UnsafeConfiguration(RuntimeError):
    pass


def assert_safe_for_environment(s: Settings) -> None:
    """正式環境禁止停用 App Check、設定 Auth Emulator、使用 * CORS 或本機刪除意圖儲存。"""
    if not s.is_production:
        return
    problems = []
    if not s.app_check_enforce:
        problems.append("正式環境不可停用 App Check 驗證")
    if os.environ.get("FIREBASE_AUTH_EMULATOR_HOST"):
        problems.append("正式環境不可設定 FIREBASE_AUTH_EMULATOR_HOST")
    if "*" in s.cors_origins or not s.cors_origins:
        problems.append("正式環境 CORS 必須是精確允許清單，不可為 * 或空")
    if s.deletion_intent_backend != "s3":
        problems.append("正式環境刪除意圖必須寫入 S3")
    if not s.db_ssl_ca:
        problems.append("正式環境必須設定 DB_SSL_CA 以驗證 RDS 憑證")
    if problems:
        raise UnsafeConfiguration("；".join(problems))
