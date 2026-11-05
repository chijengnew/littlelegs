"""條件指紋與收藏內容指紋。

- 缺省值先展開 → 固定 key 順序、固定數字／時間表示 → SHA-256。
- 年齡排序但保留重複值；偏好多選去重排序。
- 起訖識別：本專案地點用內部地點 ID；會員私人端點用內部端點 ID；訪客只有 Place ID 時用原始 Place ID
  （不改大小寫）；裝置座標只在指紋中 ROUND_HALF_UP 至小數 5 位、負零統一為零。
- 私人端點標籤不列入指紋；Google 重取資訊不列入指紋。
- 指紋規則版本 FINGERPRINT_VERSION 與 schema_version 分開；變更前須先遷移既有收藏。
"""

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.domain.schemas import Conditions

FINGERPRINT_VERSION = 1


def coord5(v: float) -> str:
    d = Decimal(repr(v)).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)
    if d == 0:
        d = Decimal("0.00000")
    return format(d, "f")


def endpoint_identity(ep: Any, private_endpoint_id: str | None = None) -> str:
    """回傳端點身分字串。會員私人端點須由呼叫端先映射成內部 ID 再傳入。"""
    if ep.type == "place_ref":
        return f"place:{ep.place_id}"
    if ep.type == "google_place":
        if private_endpoint_id:
            return f"endpoint:{private_endpoint_id}"
        return f"gplace:{ep.google_place_id}"
    if ep.type == "device_coordinate":
        return f"coord:{coord5(ep.lat)},{coord5(ep.lng)}"
    raise ValueError(f"未知端點型別 {ep.type}")


def _win(w) -> list[str] | None:
    return None if w is None else [w.start, w.end]


def canonical_conditions(c: Conditions, start_id: str, end_id: str) -> dict:
    return {
        "schema_version": c.schema_version,
        "date": c.date.isoformat(),
        "depart_time": c.depart_time,
        "return_time": c.return_time,
        "timezone": "Asia/Taipei",
        "start": start_id,
        "end": end_id,
        "travel_mode": c.travel_mode,
        "children_ages": sorted(c.children_ages),
        "nap": _win(c.nap),
        "lunch": _win(c.lunch),
        "dinner": _win(c.dinner),
        "rain_indoor_only": bool(c.rain_indoor_only),
        "facility_prefs": sorted(set(c.facility_prefs)),
        "type_prefs": sorted(set(c.type_prefs)),
    }


def _digest(obj: Any) -> bytes:
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).digest()


def conditions_fingerprint(c: Conditions, start_id: str, end_id: str) -> bytes:
    return _digest({"v": FINGERPRINT_VERSION, "c": canonical_conditions(c, start_id, end_id)})


def favorite_content_fingerprint(c: Conditions, start_id: str, end_id: str, stops: list[tuple[str, int]]) -> bytes:
    """完整條件＋起訖身分＋有序景點內部 ID＋各點停留時間。不含來源歷史 ID 或外部即時回應。"""
    return _digest(
        {
            "v": FINGERPRINT_VERSION,
            "c": canonical_conditions(c, start_id, end_id),
            "stops": [[pid, int(m)] for pid, m in stops],
        }
    )


def favorite_request_fingerprint(content_fp: bytes, saved_as: str) -> bytes:
    """冪等請求指紋：涵蓋操作不可變內容（含明確保存未驗證計畫的選擇），與內容指紋分開。"""
    return _digest({"v": FINGERPRINT_VERSION, "content": content_fp.hex(), "saved_as": saved_as})
