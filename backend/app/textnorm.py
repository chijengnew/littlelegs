"""名稱與地址正規化（NFKC、去空白與標點、簡繁與臺台統一）。

正規化結果只用於比對，不覆寫原始名稱／地址；比對鍵一律轉為正體字（臺）。
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

import opencc

_S2TW = opencc.OpenCC("s2tw")

_PUNCT_OR_SPACE = re.compile(r"[\s　]+")


def nfkc(s: str | None) -> str:
    return unicodedata.normalize("NFKC", s or "")


def norm_name(s: str | None) -> str:
    """名稱比對：NFKC → 去空白與標點/符號 → 小寫。"""
    t = nfkc(s)
    out = []
    for ch in t:
        cat = unicodedata.category(ch)
        if cat[0] in ("P", "S", "Z", "C"):
            continue
        out.append(ch)
    return "".join(out).lower()


def fold_tai(s: str) -> str:
    """臺／台 視為同字，統一為正體「臺」。只用於比對。"""
    return s.replace("台", "臺")


CITY_PREFIX = re.compile(
    r"^\s*(臺北|台北|新北|桃園|臺中|台中|臺南|台南|高雄|基隆|新竹|嘉義|苗栗|彰化|南投|雲林|屏東|宜蘭|花蓮|臺東|台東|澎湖|金門|連江|馬祖)\s*[：:]\s*"
)


def strip_city_prefix(s: str | None) -> str:
    return CITY_PREFIX.sub("", nfkc(s))


ADMIN_PREFIX = re.compile(
    r"^(國立|省立|(臺北|台北|新北|桃園|臺中|台中|臺南|台南|高雄|基隆|新竹|嘉義|苗栗|彰化|南投|雲林|屏東|宜蘭|花蓮|臺東|台東"
    r"|澎湖|金門|連江)(市立|縣立|市|縣))"
)


def strip_admin_prefix(s: str) -> str:
    rest = ADMIN_PREFIX.sub("", s, count=1)
    return s if len(rest) < 2 or rest[0] in "場集" else rest


@lru_cache(maxsize=65536)
def name_key(s: str | None) -> str:
    """名稱比對鍵：去除名稱前的縣市簡稱與行政前綴、NFKC、去空白與標點、小寫、簡體轉正體、臺台統一。"""
    return fold_tai(_S2TW.convert(norm_name(strip_admin_prefix(strip_city_prefix(s).strip()))))


_ZIP_PREFIX = re.compile(r"^\d{3,6}")
_FLOOR_TAIL = re.compile(r"(\d+樓|[bB]\d+|地下\d+樓|\(.*?\)|（.*?）|【.*?】).*$")


_ADMIN_UNIT = re.compile(r"[縣市鄉鎮區村里裡]")
_NEIGHBORHOOD = re.compile(r"\d+鄰")
_HOUSE_NO = re.compile(r"\d+(?:之\d+)?號")


def house_number_key(s: str | None) -> str | None:
    """門牌比對鍵：最後一個行政區（縣市鄉鎮區村里）之後的「路街巷弄＋號」，例如「太平巷58之1號」。

    簡繁、臺台、全半形、郵遞區號、鄰、「-」與「之」皆統一；沒有門牌號碼或缺少街道部分時回傳 None（不比對）。
    """
    t = _S2TW.convert(nfkc(s))
    t = fold_tai(_PUNCT_OR_SPACE.sub("", t)).replace("-", "之")
    t = _NEIGHBORHOOD.sub("", _ZIP_PREFIX.sub("", t))
    nums = list(_HOUSE_NO.finditer(t))
    if not nums:
        return None
    m = nums[-1]
    head = t[: m.start()]
    cut = max((u.end() for u in _ADMIN_UNIT.finditer(head)), default=0)
    street = head[cut:]
    if not street or street.isdigit():
        return None
    return street + m.group(0)


def norm_address(s: str | None) -> str:
    t = nfkc(s).strip()
    t = _PUNCT_OR_SPACE.sub("", t)
    t = _ZIP_PREFIX.sub("", t)
    t = fold_tai(t)
    t = _FLOOR_TAIL.sub("", t)
    t = t.replace("之", "-")
    return t


CITY_NAMES = [
    "臺北市",
    "新北市",
    "桃園市",
    "臺中市",
    "臺南市",
    "高雄市",
    "基隆市",
    "新竹市",
    "嘉義市",
    "新竹縣",
    "苗栗縣",
    "彰化縣",
    "南投縣",
    "雲林縣",
    "嘉義縣",
    "屏東縣",
    "宜蘭縣",
    "花蓮縣",
    "臺東縣",
    "澎湖縣",
    "金門縣",
    "連江縣",
]


def city_from_address(addr: str | None) -> str | None:
    t = nfkc(addr).replace("台", "臺")
    t = _ZIP_PREFIX.sub("", t.strip())
    for c in CITY_NAMES:
        if t.startswith(c) or c in t[:8]:
            return c
    return None
