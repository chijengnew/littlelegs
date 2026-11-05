"""UUIDv7 產生、驗證與 BINARY(16) 轉換。

- 只接受小寫、含連字號的 8-4-4-4-12 標準字串；其他表示一律視為非法（422）。
- 轉二進位採標準位元組順序（uuid.UUID.bytes），不做 UUID_TO_BIN swap_flag 的時間位交換。
- UUID 內含時間只用於期限檢查，不是身份或授權證明。
"""

from __future__ import annotations

import os
import re
import threading
import time
import uuid
from datetime import UTC, datetime

_CANONICAL = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
_CANONICAL_V4 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

_lock = threading.Lock()
_last_ms = 0
_seq = 0


def uuid7(now_ms: int | None = None) -> uuid.UUID:
    """RFC 9562 UUIDv7；同一毫秒內以 12-bit 計數維持單調遞增。"""
    global _last_ms, _seq
    with _lock:
        ms = now_ms if now_ms is not None else time.time_ns() // 1_000_000
        if ms <= _last_ms:
            ms = _last_ms
            _seq += 1
            if _seq > 0xFFF:
                ms += 1
                _seq = 0
        else:
            _seq = int.from_bytes(os.urandom(2), "big") & 0x3FF
        _last_ms = ms
        rand_b = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)
        value = (ms & ((1 << 48) - 1)) << 80
        value |= 0x7 << 76
        value |= (_seq & 0xFFF) << 64
        value |= 0b10 << 62
        value |= rand_b
        return uuid.UUID(int=value)


def new_id() -> uuid.UUID:
    return uuid7()


def is_canonical_uuid7(value: str) -> bool:
    return isinstance(value, str) and bool(_CANONICAL.match(value))


def is_canonical_uuid4(value: str) -> bool:
    return isinstance(value, str) and bool(_CANONICAL_V4.match(value))


def parse_uuid7(value: str) -> uuid.UUID:
    """嚴格解析；失敗丟 ValueError（由 API 層轉 422）。"""
    if not is_canonical_uuid7(value):
        raise ValueError("必須是小寫、含連字號的標準 UUIDv7 字串")
    return uuid.UUID(value)


def uuid7_time(u: uuid.UUID) -> datetime:
    ms = u.int >> 80
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


def to_bin(u: uuid.UUID) -> bytes:
    return u.bytes


def from_bin(b: bytes) -> uuid.UUID:
    return uuid.UUID(bytes=bytes(b))


def to_str(u: uuid.UUID) -> str:
    return str(u)
