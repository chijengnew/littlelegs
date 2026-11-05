"""資料表定義（資料模型與保存邊界）。

不保存任何 Google 名稱、地址、座標、營業時間、照片、評論、Routes 或 Weather 回應；
places 的名稱、地址與座標只來自獨立合法來源（source_records）。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BINARY, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdStr, UTCDateTime, UUIDBin

MYSQL_OPTS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}
NOW = text("CURRENT_TIMESTAMP(6)")


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (MYSQL_OPTS,)

    id: Mapped[uuid.UUID] = mapped_column(UUIDBin, primary_key=True)
    dataset_key: Mapped[str] = mapped_column(IdStr(64), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(String(512))
    license: Mapped[str] = mapped_column(String(255))
    license_url: Mapped[str | None] = mapped_column(String(512))
    license_status: Mapped[str] = mapped_column(String(16))
    license_checked_at: Mapped[Any | None] = mapped_column(Date)
    source_updated_at: Mapped[str | None] = mapped_column(String(64))
    downloaded_at: Mapped[Any | None] = mapped_column(Date)
    crs: Mapped[str | None] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(32))
    import_policy: Mapped[str] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=NOW)

    __mapper_args__ = {"eager_defaults": True}


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint("mode IN ('full','incremental')", name="ck_import_batches_mode"),
        CheckConstraint("status IN ('running','succeeded','failed','partial')", name="ck_import_batches_status"),
        MYSQL_OPTS,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDBin, primary_key=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("datasets.id"))
    mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    record_count: Mapped[int | None] = mapped_column(Integer)
    removed_count: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)


class SourceRecord(Base):
    __tablename__ = "source_records"
    __table_args__ = (
        UniqueConstraint("dataset_id", "source_key", name="uq_source_records_dataset_key"),
        Index("ix_source_records_place", "place_id"),
        MYSQL_OPTS,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDBin, primary_key=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("datasets.id"))
    source_key: Mapped[str] = mapped_column(IdStr(255))
    place_id: Mapped[uuid.UUID | None] = mapped_column(UUIDBin, ForeignKey("places.id"))
    first_batch_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("import_batches.id"))
    last_seen_batch_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("import_batches.id"))
    removed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(512))
    city: Mapped[str | None] = mapped_column(String(16))
    lat: Mapped[Decimal | None] = mapped_column(DECIMAL(9, 6))
    lon: Mapped[Decimal | None] = mapped_column(DECIMAL(9, 6))
    coord_note: Mapped[str | None] = mapped_column(String(255))
    source_updated_at: Mapped[str | None] = mapped_column(String(64))
    service_status: Mapped[int | None] = mapped_column(SmallInteger)
    public_access: Mapped[bool | None] = mapped_column(Boolean)
    display: Mapped[dict | None] = mapped_column(JSON)


class Place(Base):
    __tablename__ = "places"
    __table_args__ = (
        CheckConstraint("kind IN ('attraction','lodging')", name="ck_places_kind"),
        CheckConstraint("indoor IS NULL OR indoor IN ('indoor','outdoor','mixed')", name="ck_places_indoor"),
        CheckConstraint(
            "source_stay_minutes IS NULL OR (source_stay_minutes BETWEEN 15 AND 360 "
            "AND MOD(source_stay_minutes, 15) = 0)",
            name="ck_places_stay",
        ),
        Index("ix_places_geo", "kind", "lat", "lon"),
        Index("ix_places_name", "kind", "name"),
        MYSQL_OPTS,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDBin, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(512))
    city: Mapped[str | None] = mapped_column(String(16))
    lat: Mapped[Decimal] = mapped_column(DECIMAL(9, 6))
    lon: Mapped[Decimal] = mapped_column(DECIMAL(9, 6))
    coord_source_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDBin, ForeignKey("source_records.id", use_alter=True, name="fk_places_coord_source_record")
    )
    google_place_id: Mapped[str | None] = mapped_column(IdStr(255), unique=True)
    place_id_status: Mapped[str] = mapped_column(String(24), server_default="none")
    place_id_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    primary_type: Mapped[str | None] = mapped_column(String(32))
    indoor: Mapped[str | None] = mapped_column(String(16))
    indoor_confirmation: Mapped[str] = mapped_column(String(16), server_default="unknown")
    indoor_source_type: Mapped[str | None] = mapped_column(String(16))
    indoor_evidence_record_id: Mapped[uuid.UUID | None] = mapped_column(UUIDBin)
    indoor_evidence_note: Mapped[str | None] = mapped_column(String(512))
    indoor_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    source_stay_minutes: Mapped[int | None] = mapped_column(SmallInteger)
    source_stay_record_id: Mapped[uuid.UUID | None] = mapped_column(UUIDBin)
    service_status: Mapped[int | None] = mapped_column(SmallInteger)
    public_access: Mapped[bool | None] = mapped_column(Boolean)
    removed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=NOW)


class PlaceIdAlias(Base):
    __tablename__ = "place_id_aliases"
    __table_args__ = (MYSQL_OPTS,)

    google_place_id: Mapped[str] = mapped_column(IdStr(255), primary_key=True)
    place_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("places.id"))
    reason: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=NOW)


class PlaceType(Base):
    __tablename__ = "place_types"
    __table_args__ = (MYSQL_OPTS,)

    place_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("places.id", ondelete="CASCADE"), primary_key=True)
    type: Mapped[str] = mapped_column(String(32), primary_key=True)
    confirmation: Mapped[str] = mapped_column(String(16))
    source_type: Mapped[str] = mapped_column(String(16))
    evidence_record_id: Mapped[uuid.UUID | None] = mapped_column(UUIDBin)
    evidence_note: Mapped[str | None] = mapped_column(String(512))
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class PlaceFacility(Base):
    __tablename__ = "place_facilities"
    __table_args__ = (
        CheckConstraint("status IN ('yes','no','unknown')", name="ck_place_facilities_status"),
        MYSQL_OPTS,
    )

    place_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("places.id", ondelete="CASCADE"), primary_key=True)
    facility: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[str] = mapped_column(String(8))
    confirmation: Mapped[str] = mapped_column(String(16))
    source_type: Mapped[str] = mapped_column(String(16))
    evidence_record_id: Mapped[uuid.UUID | None] = mapped_column(UUIDBin)
    evidence_note: Mapped[str | None] = mapped_column(String(512))
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class PlaceAgeRange(Base):
    __tablename__ = "place_age_ranges"
    __table_args__ = (
        CheckConstraint(
            "min_age BETWEEN 0 AND 18 AND max_age BETWEEN 0 AND 18 AND min_age <= max_age",
            name="ck_place_age_ranges_bounds",
        ),
        MYSQL_OPTS,
    )

    place_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("places.id", ondelete="CASCADE"), primary_key=True)
    min_age: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    max_age: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    confirmation: Mapped[str] = mapped_column(String(16))
    source_type: Mapped[str] = mapped_column(String(16))
    evidence_record_id: Mapped[uuid.UUID | None] = mapped_column(UUIDBin)
    evidence_note: Mapped[str | None] = mapped_column(String(512))
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class PlaceAgeRestriction(Base):
    """來源已知「不適合」的年齡（例如明文禁止 6 歲以下）。任何一位孩子落入即排除。"""

    __tablename__ = "place_age_exclusions"
    __table_args__ = (MYSQL_OPTS,)

    place_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("places.id", ondelete="CASCADE"), primary_key=True)
    min_age: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    max_age: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(16))
    evidence_record_id: Mapped[uuid.UUID | None] = mapped_column(UUIDBin)
    evidence_note: Mapped[str | None] = mapped_column(String(512))
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("status IN ('active','deleting')", name="ck_users_status"),
        MYSQL_OPTS,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDBin, primary_key=True)
    firebase_uid: Mapped[str] = mapped_column(IdStr(128), unique=True)
    status: Mapped[str] = mapped_column(String(16), server_default="active")
    locale: Mapped[str] = mapped_column(String(16), server_default="zh-TW")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=NOW)


class PrivateEndpoint(Base):
    """會員私人端點（例如家）：只存內部 ID 與允許保存的 Place ID，不存 Google 名稱、地址或座標。"""

    __tablename__ = "private_endpoints"
    __table_args__ = (MYSQL_OPTS,)

    id: Mapped[uuid.UUID] = mapped_column(UUIDBin, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("users.id", ondelete="CASCADE"))
    google_place_id: Mapped[str] = mapped_column(IdStr(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, server_default=NOW)


class PrivateEndpointAlias(Base):
    """同一會員的 Place ID（含已確認 alias）→ 端點身分；(user_id, google_place_id) 唯一。"""

    __tablename__ = "private_endpoint_aliases"
    __table_args__ = (MYSQL_OPTS,)

    user_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    google_place_id: Mapped[str] = mapped_column(IdStr(255), primary_key=True)
    endpoint_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("private_endpoints.id", ondelete="CASCADE"))


class History(Base):
    __tablename__ = "histories"
    __table_args__ = (
        UniqueConstraint("user_id", "query_id", name="uq_histories_user_query"),
        Index("ix_histories_list", "user_id", "created_at", "id"),
        CheckConstraint(
            "status IN ('searching','succeeded','partial','failed','guest_imported')", name="ck_histories_status"
        ),
        MYSQL_OPTS,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDBin, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("users.id", ondelete="CASCADE"))
    query_id: Mapped[uuid.UUID] = mapped_column(UUIDBin)
    schema_version: Mapped[int] = mapped_column(SmallInteger)
    conditions: Mapped[dict] = mapped_column(JSON)
    conditions_fingerprint: Mapped[bytes] = mapped_column(BINARY(32))
    fingerprint_version: Mapped[int] = mapped_column(SmallInteger)
    start_label: Mapped[str | None] = mapped_column(String(20))
    end_label: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(16))
    search_run_id: Mapped[uuid.UUID | None] = mapped_column(UUIDBin)
    search_lease_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    plan_ordered: Mapped[bool] = mapped_column(Boolean, server_default=text("0"))
    revision: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    reasons: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)


class HistoryStop(Base):
    __tablename__ = "history_stops"
    __table_args__ = (
        CheckConstraint("stay_minutes BETWEEN 15 AND 360 AND MOD(stay_minutes, 15) = 0", name="ck_history_stops_stay"),
        CheckConstraint("stay_source IN ('user','source','type_default')", name="ck_history_stops_source"),
        UniqueConstraint("history_id", "place_id", name="uq_history_stops_place"),
        MYSQL_OPTS,
    )

    history_id: Mapped[uuid.UUID] = mapped_column(
        UUIDBin, ForeignKey("histories.id", ondelete="CASCADE"), primary_key=True
    )
    order_index: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    place_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("places.id"))
    stay_minutes: Mapped[int] = mapped_column(SmallInteger)
    stay_source: Mapped[str] = mapped_column(String(16))
    day_index: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    selected_google_place_id: Mapped[str | None] = mapped_column(IdStr(255))


class QueryOperation(Base):
    """防止刪除歷史後的延遲重送重新建立。保存至操作窗口結束。"""

    __tablename__ = "query_operations"
    __table_args__ = (
        CheckConstraint("state IN ('created','deleted')", name="ck_query_operations_state"),
        Index("ix_query_operations_expiry", "expires_at"),
        MYSQL_OPTS,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    query_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, primary_key=True)
    request_fingerprint: Mapped[bytes] = mapped_column(BINARY(32))
    fingerprint_version: Mapped[int] = mapped_column(SmallInteger)
    state: Mapped[str] = mapped_column(String(16))
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "content_fingerprint", name="uq_favorites_user_content"),
        Index("ix_favorites_list", "user_id", "created_at", "id"),
        CheckConstraint("saved_as IN ('plan','unverified','infeasible')", name="ck_favorites_saved_as"),
        MYSQL_OPTS,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDBin, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("users.id", ondelete="CASCADE"))
    content_fingerprint: Mapped[bytes] = mapped_column(BINARY(32))
    fingerprint_version: Mapped[int] = mapped_column(SmallInteger)
    source_history_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDBin, ForeignKey("histories.id", ondelete="SET NULL")
    )
    schema_version: Mapped[int] = mapped_column(SmallInteger)
    conditions: Mapped[dict] = mapped_column(JSON)
    start_label: Mapped[str | None] = mapped_column(String(20))
    end_label: Mapped[str | None] = mapped_column(String(20))
    saved_as: Mapped[str] = mapped_column(String(16))
    reasons: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class FavoriteStop(Base):
    __tablename__ = "favorite_stops"
    __table_args__ = (
        CheckConstraint("stay_minutes BETWEEN 15 AND 360 AND MOD(stay_minutes, 15) = 0", name="ck_favorite_stops_stay"),
        CheckConstraint("stay_source IN ('user','source','type_default')", name="ck_favorite_stops_source"),
        MYSQL_OPTS,
    )

    favorite_id: Mapped[uuid.UUID] = mapped_column(
        UUIDBin, ForeignKey("favorites.id", ondelete="CASCADE"), primary_key=True
    )
    order_index: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    place_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("places.id"))
    stay_minutes: Mapped[int] = mapped_column(SmallInteger)
    stay_source: Mapped[str] = mapped_column(String(16))
    day_index: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    selected_google_place_id: Mapped[str | None] = mapped_column(IdStr(255))


class FavoriteOperation(Base):
    """收藏冪等操作紀錄。favorite_id 不設外鍵：收藏刪除後紀錄仍需存在以防復活。"""

    __tablename__ = "favorite_operations"
    __table_args__ = (
        CheckConstraint("op_type IN ('create','delete')", name="ck_favorite_operations_type"),
        CheckConstraint("state IN ('completed','cancelled')", name="ck_favorite_operations_state"),
        Index("ix_favorite_operations_target", "user_id", "favorite_id"),
        Index("ix_favorite_operations_expiry", "expires_at"),
        MYSQL_OPTS,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(UUIDBin, primary_key=True)
    op_type: Mapped[str] = mapped_column(String(16))
    request_fingerprint: Mapped[bytes] = mapped_column(BINARY(32))
    fingerprint_version: Mapped[int] = mapped_column(SmallInteger)
    state: Mapped[str] = mapped_column(String(16))
    favorite_id: Mapped[uuid.UUID | None] = mapped_column(UUIDBin)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class FavoriteAlias(Base):
    """指紋升版合併時，舊收藏 ID 以最小 alias 指向保留者。"""

    __tablename__ = "favorite_aliases"
    __table_args__ = (MYSQL_OPTS,)

    old_favorite_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("users.id", ondelete="CASCADE"))
    favorite_id: Mapped[uuid.UUID] = mapped_column(UUIDBin, ForeignKey("favorites.id", ondelete="CASCADE"))


class Feedback(Base):
    """訪客與會員的回饋。不主動關聯會員帳號；內容與信箱仍可能含個人資料，保存期限見 services/feedback.py。"""

    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("type IN ('bug','place_data','suggestion','other')", name="ck_feedback_type"),
        CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_feedback_rating"),
        CheckConstraint(
            "source_page IN ('planner','place_detail','saved_detail','footer','other')", name="ck_feedback_source"
        ),
        Index("ix_feedback_created_at", "created_at"),
        MYSQL_OPTS,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDBin, primary_key=True)
    type: Mapped[str] = mapped_column(String(16))
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    content: Mapped[str] = mapped_column(String(1000))
    contact_email: Mapped[str | None] = mapped_column(String(254))
    source_page: Mapped[str] = mapped_column(String(16))
    place_id: Mapped[uuid.UUID | None] = mapped_column(UUIDBin, ForeignKey("places.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


class RateCounter(Base):
    __tablename__ = "rate_counters"
    __table_args__ = (Index("ix_rate_counters_expiry", "purge_after"), MYSQL_OPTS)

    counter_key: Mapped[str] = mapped_column(IdStr(191), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(UTCDateTime, primary_key=True)
    count: Mapped[int] = mapped_column(BigInteger)
    purge_after: Mapped[datetime] = mapped_column(UTCDateTime)
