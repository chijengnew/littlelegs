"""旅宿親子設施擷取。

只承認可追溯資料「明確記載」的嬰兒床、嬰兒澡盆、兒童遊戲空間：
- 結構化服務標籤 ServiceInfo「兒童遊樂設施」→ kids_play_area = yes（confirmed）。
- 文字欄位以規則擷取；否定語句 → no，附條件語句（需預約、數量有限、加價…）或無法判斷 → unknown。
- 不從名稱、照片或評分推定。
"""

from __future__ import annotations

import re

from .model import Attr

TERMS: dict[str, re.Pattern[str]] = {
    "crib": re.compile(r"(嬰兒床|嬰兒小床|嬰兒睡床|寶寶床)(?!圍)"),
    "baby_bathtub": re.compile(r"(嬰兒澡盆|嬰兒浴盆|嬰兒洗澡盆|新生兒洗澡盆|寶寶澡盆|嬰兒浴缸)"),
    "kids_play_area": re.compile(
        r"(兒童遊戲室|兒童遊戲區|兒童遊樂區|兒童遊戲空間|兒童遊戲場|兒童遊樂場|親子遊戲室|親子遊戲區|兒童遊憩區|兒童遊樂室)"
    ),
}

NEGATION = re.compile(
    r"(不提供|無提供|未提供|沒有提供|無法提供|停止提供|暫停提供|恕不|不含|不設|未設|沒有|無設置|並無)"
)
CONDITIONAL = re.compile(
    r"(需預約|須預約|請預約|先預約|需事先|須事先|請事先|如有需要|如需|若需|數量有限|有限數量|另計|加價|收費|酌收|"
    r"視情況|依房型|部分房型|特定房型|僅限|限量|租借|借用|需告知|請告知|請洽|洽詢|另行)"
)
SENTENCE_SPLIT = re.compile(r"[。！!？?；;\n\r✅◆★●■※▲▶►•｜|]+")

KIDS_PLAY_TAG = "兒童遊樂設施"
NURSING_TAG = "哺乳室"


def _scan_text(text: str, field_name: str) -> dict[str, Attr]:
    found: dict[str, Attr] = {}
    for sentence in SENTENCE_SPLIT.split(text or ""):
        s = sentence.strip()
        if not s:
            continue
        for fac, pat in TERMS.items():
            m = pat.search(s)
            if not m:
                continue
            snippet = s[max(0, m.start() - 20) : m.end() + 20]
            before = s[: m.start()]
            if NEGATION.search(before[-12:]):
                attr = Attr("no", "confirmed", f"{field_name}: 否定語句「{snippet}」")
            elif NEGATION.search(before):
                attr = Attr("unknown", "unknown", f"{field_name}: 同句含否定詞，無法判斷「{snippet}」")
            elif CONDITIONAL.search(s):
                attr = Attr("unknown", "unknown", f"{field_name}: 附條件語句「{snippet}」")
            else:
                attr = Attr("yes", "confirmed", f"{field_name}: 「{snippet}」")
            prev = found.get(fac)
            if prev is None:
                found[fac] = attr
            elif prev.value != attr.value:
                found[fac] = Attr("unknown", "unknown", f"{field_name}: 多處敘述不一致")
    return found


def extract(service_info: str | None, description: str | None, room_info: str | None) -> dict[str, Attr]:
    result: dict[str, Attr] = {}
    tags = [t.strip() for t in re.split(r"[,，]", service_info or "") if t.strip()]
    if KIDS_PLAY_TAG in tags:
        result["kids_play_area"] = Attr("yes", "confirmed", f"ServiceInfo 標籤「{KIDS_PLAY_TAG}」")
    if NURSING_TAG in tags:
        result["nursing_room"] = Attr("yes", "confirmed", f"ServiceInfo 標籤「{NURSING_TAG}」")

    text_hits: dict[str, Attr] = {}
    for fname, text in (("Description", description), ("RoomInfo", room_info)):
        for fac, attr in _scan_text(text or "", fname).items():
            prev = text_hits.get(fac)
            if prev is None:
                text_hits[fac] = attr
            elif prev.value != attr.value:
                text_hits[fac] = Attr("unknown", "unknown", "Description/RoomInfo 敘述不一致")
    for fac, attr in text_hits.items():
        if fac in result:
            continue
        result[fac] = attr
    return result


def family_label(facilities: dict[str, Attr]) -> list[str]:
    """回傳已確認的親子設施清單（至少一項才可列「有親子設施資訊」）。"""
    return [
        f
        for f in ("crib", "baby_bathtub", "kids_play_area")
        if (a := facilities.get(f)) is not None and a.value == "yes" and a.confirmation == "confirmed"
    ]
