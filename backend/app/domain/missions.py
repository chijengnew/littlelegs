"""任務定義與進度計算（受版本控制的簡單定義，不是規則引擎）。

- 只支援 distinct_places：不重複、定位核對成功的景點數達門檻，可限定一組主要類型代碼。
- 只計入未下架的景點：整併時被併入的舊地點會下架，因此同一實體不會因整併重複計數；
  無法確認是否同一實體的下架景點一律不計入。手動紀錄只出現在護照，不計入任務。
- 進度與解鎖狀態每次依目前紀錄即時計算；刪除紀錄或景點分類調整後隨之改變，不保留歷史徽章。
- 任務名稱與說明放在前端翻譯檔，以 code 對應。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import get_args

from app.domain.schemas import TypePref

KINDS = ("distinct_places",)


@dataclass(frozen=True)
class Mission:
    code: str
    kind: str
    threshold: int
    types: tuple[str, ...] = ()


MISSIONS: tuple[Mission, ...] = (
    Mission("first_stamp", "distinct_places", 1),
    Mission("park_explorer", "distinct_places", 3, ("park_playground",)),
    Mission("culture_scholar", "distinct_places", 2, ("museum",)),
    Mission("little_explorer", "distinct_places", 5),
)


def validate(missions: Iterable[Mission]) -> None:
    known = set(get_args(TypePref))
    seen: set[str] = set()
    for m in missions:
        if not m.code or not m.code.replace("_", "").isalnum() or not m.code.islower():
            raise ValueError(f"任務代碼格式錯誤：{m.code!r}")
        if m.code in seen:
            raise ValueError(f"任務代碼重複：{m.code}")
        seen.add(m.code)
        if m.kind not in KINDS:
            raise ValueError(f"不支援的任務條件：{m.kind}")
        if m.threshold < 1:
            raise ValueError(f"任務門檻必須至少 1：{m.code}")
        unknown = set(m.types) - known
        if unknown:
            raise ValueError(f"任務 {m.code} 使用未定義的類型代碼：{sorted(unknown)}")


validate(MISSIONS)


@dataclass(frozen=True)
class CountedPlace:
    place_id: str
    primary_type: str | None


def progress(mission: Mission, places: Iterable[CountedPlace]) -> int:
    ids = {p.place_id for p in places if not mission.types or p.primary_type in mission.types}
    return len(ids)
