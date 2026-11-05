"""SQLAlchemy 2.0 宣告式基底與共用型別。

- 主要實體 UUIDv7 存 BINARY(16)（標準位元組順序）。
- 識別碼字串（Firebase UID、Place ID、計數鍵）使用 utf8mb4_0900_bin 精確比較，不做大小寫或尾端空白正規化。
- 時間點一律 UTC，存 DATETIME(6)（naive，約定為 UTC）；連線 time_zone 設為 +00:00。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import String, TypeDecorator
from sqlalchemy.dialects.mysql import BINARY, DATETIME
from sqlalchemy.orm import DeclarativeBase


class UUIDBin(TypeDecorator):
    impl = BINARY(16)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value.bytes
        if isinstance(value, (bytes, bytearray)) and len(value) == 16:
            return bytes(value)
        raise TypeError(f"UUIDBin 需要 uuid.UUID，收到 {type(value)!r}")

    def process_result_value(self, value, dialect):
        return None if value is None else uuid.UUID(bytes=bytes(value))


class UTCDateTime(TypeDecorator):
    """寫入前轉 UTC 並去掉 tzinfo；讀出後補回 UTC。不依賴驅動或 MySQL 隱式時區轉換。"""

    impl = DATETIME(fsp=6)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("時間點必須帶時區（naive datetime 不允許寫入）")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        return None if value is None else value.replace(tzinfo=UTC)


def rowcount(result) -> int:
    """DML 影響列數（CursorResult.rowcount）；不可當作限流計數使用。"""
    return int(getattr(result, "rowcount", 0) or 0)


def IdStr(length: int) -> String:  # noqa: N802
    """精確比較的識別碼字串欄位。"""
    return String(length, collation="utf8mb4_0900_bin")


class Base(DeclarativeBase):
    pass
