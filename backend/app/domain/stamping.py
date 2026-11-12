"""景點蓋章：請求格式、定位核對與冪等請求指紋。

- 請求座標與 accuracy_m 都是用戶端宣稱值：只驗證格式、範圍與非 NaN／Infinity，再與資料庫中
  獨立來源的景點參考點比較球面距離。瀏覽器定位可被模擬，這只是親子遊戲的合理位置檢查，不是防作弊機制。
- 座標只在當次請求記憶體中使用：不寫入資料庫、冪等紀錄、錯誤回應或日誌。
- 請求指紋只含景點與核對方式，不含座標與精確度（景點位置已知，150 公尺內的座標可被暴力推回）。
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.config import Stamping
from app.domain.schemas import StrictModel, _uuid7_str
from app.errors import ApiError
from app.geo import haversine_m

FINGERPRINT_VERSION = 1
Method = Literal["location", "manual"]
Outcome = Literal["created", "upgraded", "existing"]


class LocationIn(StrictModel):
    lat: float = Field(strict=True, ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(strict=True, ge=-180, le=180, allow_inf_nan=False)
    accuracy_m: float = Field(strict=True, gt=0, le=100_000, allow_inf_nan=False)


class CheckInIn(StrictModel):
    place_id: str
    verification_method: Method
    location: LocationIn | None = None

    @field_validator("place_id")
    @classmethod
    def _pid(cls, v: str) -> str:
        return _uuid7_str(v)

    @model_validator(mode="after")
    def _location_matches_method(self) -> CheckInIn:
        if self.verification_method == "location" and self.location is None:
            raise ValueError("定位核對需要附上本次定位結果")
        if self.verification_method == "manual" and self.location is not None:
            raise ValueError("手動紀錄不接受定位資料")
        return self


def check_location(place_lat: float, place_lon: float, loc: LocationIn, rules: Stamping) -> None:
    """精確度或距離不符門檻時拋出錯誤；錯誤只說明門檻，不回傳計算出的距離或位置。"""
    if loc.accuracy_m > rules.max_accuracy_m:
        raise ApiError(
            422,
            "LOCATION_INACCURATE",
            f"這次定位的精確度不足（需要在 {rules.max_accuracy_m:g} 公尺內），請到空曠處重新定位，或改用手動紀錄",
        )
    if haversine_m(loc.lat, loc.lng, place_lat, place_lon) > rules.max_distance_m:
        raise ApiError(
            422,
            "LOCATION_TOO_FAR",
            f"目前位置離景點參考點超過 {rules.max_distance_m:g} 公尺，請靠近景點後重新定位，或改用手動紀錄",
        )


def request_fingerprint(place_id: str, method: str) -> bytes:
    body = json.dumps(
        {"v": FINGERPRINT_VERSION, "place_id": place_id, "method": method}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(body.encode("utf-8")).digest()
