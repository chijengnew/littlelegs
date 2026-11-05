"""各資料集讀取與清洗。每個 loader 回傳 (SourceRec 清單, FacilityPoint 清單, Exclusion 清單)。

原則：
- 只用獨立來源欄位；座標系統依資料集說明轉換，不假定全部是 WGS84。
- 沒有座標的紀錄不人工補登；標為 match_only，交由 resolve 與有座標地點配對，未配對即排除。
- 未知以 None／unknown 表示，不以 false 混同。
"""

from __future__ import annotations

import csv
import io
import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import date
from pathlib import Path

from app.geo import in_taiwan
from app.textnorm import city_from_address, nfkc, norm_name

from . import lodging_facilities
from .model import Attr, Exclusion, FacilityPoint, SourceRec

Loaded = tuple[list[SourceRec], list[FacilityPoint], list[Exclusion]]

TDX_CLASS_NAMES = {
    1: "文化類",
    2: "生態類",
    3: "文化資產類",
    4: "宗教廟宇類",
    5: "藝術類",
    6: "商圈商店類",
    7: "國家公園類",
    8: "國家風景區類",
    9: "休閒農業類",
    10: "溫泉類",
    11: "自然風景類",
    12: "遊憩類",
    13: "體育健身類",
    14: "觀光工廠類",
    15: "都會公園類",
    16: "森林遊樂區類",
    17: "平地森林園區類",
    18: "國家自然公園類",
    19: "公園綠地類",
    20: "觀光遊樂業類",
    21: "原住民文化類",
    22: "客家文化類",
    23: "交通場站類",
    24: "水域環境類",
    25: "藝文場館類",
    26: "生態場館類",
    27: "娛樂場館類",
    254: "其他",
}

INDOOR_BY_TYPE = {"museum": "indoor", "tourism_factory": "indoor", "parent_child_center": "indoor"}
OUTDOOR_BY_TYPE = {"park_playground": "outdoor"}

MUSEUM_NAME = re.compile(r"(博物館|博物院|美術館|科學館|科學教育館|科教館)")
PARENT_CHILD_NAME = re.compile(r"親子館")
PARK_NAME = re.compile(r"(公園|綠地|遊戲場|遊樂|樂園|森林|步道|河濱|廣場|植物園|花園|苗圃|親水|濕地|溼地)")


def _f(v) -> float | None:
    try:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _coords(
    dataset: str, key: str, name: str, lat, lon, excl: list[Exclusion], required: bool = False
) -> tuple[float | None, float | None, bool]:
    """回傳 (lat, lon, ok)。越界一律記錄排除；缺座標只有 required=True 時記錄排除
    （match_only 資料集缺座標不是錯誤，交由 resolve 配對）。"""
    la, lo = _f(lat), _f(lon)
    if la is None or lo is None or (la == 0 and lo == 0):
        if required:
            excl.append(Exclusion(dataset, key, name, "缺座標"))
        return None, None, False
    if not in_taiwan(la, lo):
        excl.append(Exclusion(dataset, key, name, f"座標不在台灣服務範圍或經緯度顛倒（{la},{lo}）；不自動修正"))
        return None, None, False
    return round(la, 6), round(lo, 6), True


def _type_inference(rec: SourceRec) -> None:
    """依類型補室內外推定（必須標 inferred）。"""
    if rec.indoor is not None:
        return
    for t, v in {**INDOOR_BY_TYPE, **OUTDOOR_BY_TYPE}.items():
        if t in rec.types:
            rec.indoor = Attr(v, "inferred", f"依類型 {t} 推定，非場勘")
            return


def _read_csv(path: Path, encoding: str, strip_double_bom: bool = False) -> list[dict[str, str]]:
    raw = path.read_bytes()
    while strip_double_bom and raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    text = raw.decode(encoding)
    text = text.lstrip("﻿")
    rows = list(csv.DictReader(io.StringIO(text)))
    return [r for r in rows if any((v or "").strip() for v in r.values())]


def load_tdx_attractions(raw: Path) -> Loaded:
    ds = "tdx_attractions"
    data = json.loads((raw / "AttractionList.json").read_text(encoding="utf-8-sig"))["Attractions"]
    st = json.loads((raw / "AttractionServiceTimeList.json").read_text(encoding="utf-8-sig"))["AttractionServiceTimes"]
    fees = json.loads((raw / "AttractionFeeList.json").read_text(encoding="utf-8-sig"))["AttractionFees"]
    st_by = {x["AttractionID"]: x["ServiceTimes"] for x in st}
    fee_by = {x["AttractionID"]: x["Fees"] for x in fees}

    recs: list[SourceRec] = []
    excl: list[Exclusion] = []
    seen: set[str] = set()
    for a in data:
        key = a["AttractionID"]
        name = (a.get("AttractionName") or "").strip()
        if key in seen:
            excl.append(Exclusion(ds, key, name, "AttractionID 重複"))
            continue
        seen.add(key)
        classes = [int(c) for c in (a.get("AttractionClasses") or [])]
        if a.get("ServiceStatus") == 0:
            excl.append(Exclusion(ds, key, name, "ServiceStatus=0 永久停止營運"))
            continue
        if classes and set(classes) <= {23}:
            excl.append(Exclusion(ds, key, name, "僅屬交通場站類，非親子景點"))
            continue
        lat, lon, ok = _coords(ds, key, name, a.get("PositionLat"), a.get("PositionLon"), excl, required=True)
        if not ok:
            continue
        addr = a.get("PostalAddress") or {}
        full_addr = f"{addr.get('City') or ''}{addr.get('Town') or ''}{addr.get('StreetAddress') or ''}" or None
        rec = SourceRec(
            ds,
            key,
            name,
            "attraction",
            address=full_addr,
            city=addr.get("City") or city_from_address(full_addr),
            lat=lat,
            lon=lon,
        )
        if 14 in classes:
            rec.types["tourism_factory"] = Attr(True, "confirmed", "AttractionClasses=14 觀光工廠類")
        if classes and set(classes) & {15, 19} and PARK_NAME.search(name):
            rec.types["park_playground"] = Attr(
                True, "confirmed", "AttractionClasses 含 15 都會公園類／19 公園綠地類，且名稱含公園相關字樣"
            )
        if MUSEUM_NAME.search(name):
            rec.types["museum"] = Attr(True, "inferred", "名稱含博物館／美術館／科學館")
        if PARENT_CHILD_NAME.search(name):
            rec.types["parent_child_center"] = Attr(True, "inferred", "名稱含「親子館」")
        vd = a.get("VisitDuration")
        if isinstance(vd, int) and vd > 0:
            rec.stay_minutes_raw = vd
        rec.service_status = a.get("ServiceStatus")
        rec.public_access = None if a.get("IsPublicAccess") is None else bool(a.get("IsPublicAccess"))
        rec.source_updated_at = a.get("UpdateTime")
        rec.display = {
            "description": (a.get("Description") or "")[:3000],
            "telephones": [t.get("Tel") for t in (a.get("Telephones") or []) if t.get("Tel")],
            "website": a.get("WebsiteURL") or None,
            "service_time_info": a.get("ServiceTimeInfo") or None,
            "fee_info": a.get("FeeInfo") or None,
            "parking_info": a.get("ParkingInfo") or None,
            "is_accessible_for_free": a.get("IsAccessibleForFree"),
            "attraction_classes": [TDX_CLASS_NAMES.get(c, str(c)) for c in classes],
            "source_service_times": st_by.get(key),
            "source_fees": fee_by.get(key),
            "visit_duration_raw": vd,
        }
        _type_inference(rec)
        recs.append(rec)
    return recs, [], excl


def load_tdx_hotels(raw: Path) -> Loaded:
    ds = "tdx_hotels"
    data = json.loads((raw / "HotelList.json").read_text(encoding="utf-8-sig"))["Hotels"]
    recs: list[SourceRec] = []
    excl: list[Exclusion] = []
    for h in data:
        key = h["HotelID"]
        name = (h.get("HotelName") or "").strip()
        if h.get("ServiceStatus") == 0:
            excl.append(Exclusion(ds, key, name, "ServiceStatus=0 永久停止營運"))
            continue
        lat, lon, ok = _coords(ds, key, name, h.get("PositionLat"), h.get("PositionLon"), excl, required=True)
        if not ok:
            continue
        addr = h.get("PostalAddress") or {}
        full_addr = f"{addr.get('City') or ''}{addr.get('Town') or ''}{addr.get('StreetAddress') or ''}" or None
        rec = SourceRec(ds, key, name, "lodging", address=full_addr, city=addr.get("City"), lat=lat, lon=lon)
        rec.facilities = lodging_facilities.extract(h.get("ServiceInfo"), h.get("Description"), h.get("RoomInfo"))
        rec.service_status = h.get("ServiceStatus")
        rec.source_updated_at = h.get("UpdateTime")
        rec.display = {
            "license_number": h.get("HotelLicenseNumber"),
            "hotel_classes": h.get("HotelClasses"),
            "telephones": [t.get("Tel") for t in (h.get("Telephones") or []) if t.get("Tel")],
            "website": h.get("WebsiteURL") or None,
            "lowest_price": h.get("LowestPrice"),
            "ceiling_price": h.get("CeilingPrice"),
            "service_tags": [t.strip() for t in re.split(r"[,，]", h.get("ServiceInfo") or "") if t.strip()],
            "parking_info": h.get("ParkingInfo") or None,
        }
        recs.append(rec)
    return recs, [], excl


def load_taipei_attractions(raw: Path) -> Loaded:
    ds = "taipei_attractions"
    data = json.loads((raw / "taipei_attractions.json").read_text(encoding="utf-8-sig"))["data"]
    recs: list[SourceRec] = []
    excl: list[Exclusion] = []
    for a in data:
        key = str(a["id"])
        name = (a.get("name") or "").strip()
        lat, lon, ok = _coords(ds, key, name, a.get("nlat"), a.get("elong"), excl, required=True)
        if not ok:
            continue
        addr = nfkc(a.get("address") or "").strip() or None
        rec = SourceRec(ds, key, name, "attraction", address=addr, city=city_from_address(addr), lat=lat, lon=lon)
        friendly = [f.get("name") for f in (a.get("friendly") or [])]
        if "哺(集)乳友善" in friendly:
            rec.facilities["nursing_room"] = Attr("yes", "confirmed", "friendly 含「哺(集)乳友善」")
        if MUSEUM_NAME.search(name):
            rec.types["museum"] = Attr(True, "inferred", "名稱含博物館／美術館／科學館")
        if PARENT_CHILD_NAME.search(name):
            rec.types["parent_child_center"] = Attr(True, "inferred", "名稱含「親子館」")
        rec.source_updated_at = a.get("modified")
        rec.display = {
            "description": (a.get("introduction") or "")[:3000],
            "open_time": a.get("open_time") or None,
            "telephones": [a["tel"]] if a.get("tel") else [],
            "website": a.get("official_site") or None,
            "source_url": a.get("url"),
            "ticket": a.get("ticket") or None,
            "categories": [c.get("name") for c in (a.get("category") or [])],
            "targets": [c.get("name") for c in (a.get("target") or [])],
            "staytime_text": a.get("staytime") or None,
        }
        _type_inference(rec)
        recs.append(rec)
    return recs, [], excl


def load_tainan_attractions(raw: Path) -> Loaded:
    ds = "tainan_attractions"
    data = json.loads((raw / "tainan_attractions.json").read_text(encoding="utf-8-sig"))
    recs: list[SourceRec] = []
    excl: list[Exclusion] = []
    for a in data:
        key = str(a["id"])
        name = (a.get("name") or "").strip()
        lat, lon, ok = _coords(ds, key, name, a.get("lat"), a.get("long"), excl, required=True)
        if not ok:
            continue
        addr = nfkc(a.get("address") or "").strip() or None
        rec = SourceRec(ds, key, name, "attraction", address=addr, city="臺南市", lat=lat, lon=lon)
        if MUSEUM_NAME.search(name):
            rec.types["museum"] = Attr(True, "inferred", "名稱含博物館／美術館／科學館")
        rec.source_updated_at = a.get("update_time")
        rec.display = {
            "description": (a.get("summary") or a.get("introduction") or "")[:3000],
            "open_time": a.get("open_time") or None,
            "telephones": [a["tel"]] if a.get("tel") else [],
            "categories": a.get("category") or [],
        }
        _type_inference(rec)
        recs.append(rec)
    return recs, [], excl


def load_taoyuan_attractions(raw: Path) -> Loaded:
    ds = "taoyuan_attractions"
    root = ET.parse(raw / "taoyuan_attractions.xml").getroot()
    recs: list[SourceRec] = []
    excl: list[Exclusion] = []
    for info in root.findall("Info"):

        def g(tag: str, _info=info) -> str:
            return (_info.findtext(tag) or "").strip()

        key, name = g("InfoId"), g("Name")
        lat, lon, ok = _coords(ds, key, name, g("Py"), g("Px"), excl, required=True)
        if not ok:
            continue
        addr = nfkc(g("Add")) or None
        rec = SourceRec(ds, key, name, "attraction", address=addr, city="桃園市", lat=lat, lon=lon)
        if MUSEUM_NAME.search(name):
            rec.types["museum"] = Attr(True, "inferred", "名稱含博物館／美術館／科學館")
        rec.source_updated_at = g("Changetime") or None
        rec.display = {
            "description": g("Toldescribe")[:3000],
            "open_time": g("Opentime") or None,
            "ticket": g("Ticketinfo") or None,
            "telephones": [g("Tel")] if g("Tel") else [],
            "website": g("Website") or None,
            "source_url": g("TYWebsite") or None,
            "parking_info": g("Parkinginfo") or None,
        }
        _type_inference(rec)
        recs.append(rec)
    return recs, [], excl


def load_hsinchu_city_attractions(raw: Path) -> Loaded:
    ds = "hsinchu_city_attractions"
    recs = []
    for r in _read_csv(raw / "hsinchu_city_attractions.csv", "utf-8"):
        name = (r.get("景點名稱") or "").strip()
        addr = nfkc(r.get("地址") or "").strip() or None
        rec = SourceRec(ds, name, name, "attraction", address=addr, city="新竹市")
        if MUSEUM_NAME.search(name):
            rec.types["museum"] = Attr(True, "inferred", "名稱含博物館／美術館／科學館")
        rec.display = {"description": (r.get("景點介紹") or "")[:3000]}
        _type_inference(rec)
        recs.append(rec)
    return recs, [], []


def load_tw_museums(raw: Path) -> Loaded:
    import xlrd

    ds = "tw_museums"
    sh = xlrd.open_workbook(str(raw / "tw_museums.xls")).sheet_by_index(0)
    head = [h.strip() for h in sh.row_values(0)]
    recs: list[SourceRec] = []
    excl: list[Exclusion] = []
    for i in range(1, sh.nrows):
        r = dict(zip(head, sh.row_values(i), strict=False))
        key = str(r.get("mainTypePK") or "").strip()
        name = str(r.get("名稱") or "").strip()
        lat, lon, _ok = _coords(ds, key, name, r.get("緯度"), r.get("經度"), excl)
        addr = nfkc(str(r.get("地址") or "")).strip() or None
        rec = SourceRec(
            ds,
            key,
            name,
            "attraction",
            address=addr,
            city=(str(r.get("縣市") or "").strip() or city_from_address(addr)),
            lat=lat,
            lon=lon,
        )
        rec.types["museum"] = Attr(True, "confirmed", "文化部全國博物館資料集（主類別：博物館）")
        rec.display = {
            "ticket": str(r.get("票價") or "").strip() or None,
            "telephones": [str(r["電話"]).strip()] if r.get("電話") else [],
            "website": str(r.get("網站") or "").strip() or None,
            "closed_days": str(r.get("休館日") or "").strip() or None,
        }
        _type_inference(rec)
        recs.append(rec)
    return recs, [], excl


def load_leisure_agri(raw: Path) -> Loaded:
    ds = "tw_leisure_agri_areas"
    data = json.loads((raw / "tw_leisure_agri_areas.json").read_text(encoding="utf-8-sig"))
    recs: list[SourceRec] = []
    excl: list[Exclusion] = []
    for a in data:
        key = str(a.get("Record_ID") or a.get("ID"))
        name = (a.get("Name") or "").strip()
        lat, lon, ok = _coords(ds, key, name, a.get("Latitude"), a.get("Longitude"), excl, required=True)
        if not ok:
            continue
        addr = f"{a.get('County') or ''}{a.get('Town') or ''}{a.get('Address') or ''}" or None
        rec = SourceRec(
            ds,
            key,
            name,
            "attraction",
            address=addr,
            city=a.get("County"),
            lat=lat,
            lon=lon,
            coord_note="休閒農業區代表點，非單一場館入口",
        )
        oh = a.get("OpenHours")
        rec.display = {
            "description": (a.get("Introduction") or "")[:3000],
            "open_time": None if oh in (None, "", "None") else oh,
            "telephones": [a["Tel"]] if a.get("Tel") else [],
        }
        recs.append(rec)
    return recs, [], excl


def load_tourism_factories(raw: Path) -> Loaded:
    ds = "tw_tourism_factories"
    recs: list[SourceRec] = []
    excl: list[Exclusion] = []
    for r in _read_csv(raw / "tw_tourism_factories.csv", "utf-8"):
        name = (r.get("觀光工廠名稱") or "").strip()
        if "休館" in name:
            excl.append(Exclusion(ds, name, name, "名稱含「休館」"))
            continue
        addr = nfkc(r.get("地址") or "").strip() or None
        rec = SourceRec(ds, name, name, "attraction", address=addr, city=(r.get("縣市") or "").strip() or None)
        rec.types["tourism_factory"] = Attr(True, "confirmed", "經濟部觀光工廠資料集")
        rec.display = {
            "telephones": [r["觀光工廠預約電話"]] if r.get("觀光工廠預約電話") else [],
            "website": r.get("網址") or None,
        }
        _type_inference(rec)
        recs.append(rec)
    return recs, [], excl


ENV_EDU_EXCLUDE = re.compile(
    r"(焚化|垃圾|污水|汙水|水資源回收|掩埋|廢棄物|廢水|處理廠|處理場|資源回收廠|再生能源廠|下水道|衛生掩埋|環保科技園區|資源化)"
)


def load_env_edu(raw: Path, today: date) -> Loaded:
    ds = "tw_env_edu_sites"
    recs: list[SourceRec] = []
    excl: list[Exclusion] = []
    for r in _read_csv(raw / "tw_env_edu_sites.csv", "utf-8"):
        key = (r.get("license_no") or "").strip() or (r.get("org_name") or "").strip()
        name = (r.get("org_name") or "").strip()
        vd = (r.get("valid_date") or "").strip()
        try:
            y, m, d = (int(x) for x in vd.split("/"))
            if date(y, m, d) < today:
                excl.append(Exclusion(ds, key, name, f"環境教育認證已過期（valid_date={vd}）"))
                continue
        except ValueError:
            excl.append(Exclusion(ds, key, name, f"valid_date 無法解析（{vd}）"))
            continue
        if ENV_EDU_EXCLUDE.search(name):
            excl.append(Exclusion(ds, key, name, "非親子場所（焚化／污水／掩埋等處理設施）"))
            continue
        addr = nfkc(r.get("address") or "").strip() or None
        rec = SourceRec(ds, key, name, "attraction", address=addr, city=city_from_address(addr))
        rec.types["env_edu"] = Attr(True, "confirmed", f"環境教育設施場所認證 {r.get('license_no')}（至 {vd}）")
        rec.display = {"env_edu_valid_until": vd}
        recs.append(rec)
    return recs, [], excl


def load_parent_child_centers(raw: Path) -> Loaded:
    ds = "taipei_parent_child_centers"
    recs = []
    for r in _read_csv(raw / "taipei_parent_child_centers.csv", "utf-8"):
        name = (r.get("機構名稱") or "").strip()
        addr = nfkc(r.get("地址") or "").strip() or None
        rec = SourceRec(ds, name, name, "attraction", address=addr, city="臺北市")
        rec.types["parent_child_center"] = Attr(True, "confirmed", "臺北市親子館資料集")
        rec.display = {"telephones": [r["電話"]] if r.get("電話") else []}
        _type_inference(rec)
        recs.append(rec)
    return recs, [], []


def load_taipei_park_facility(raw: Path) -> Loaded:
    from pyproj import Transformer

    ds = "taipei_park_facility"
    tf = Transformer.from_crs("EPSG:3826", "EPSG:4326", always_xy=True)
    data = json.loads((raw / "taipei_park_facility.json").read_text(encoding="utf-8-sig"))
    recs: list[SourceRec] = []
    excl: list[Exclusion] = []
    seen: dict[str, SourceRec] = {}
    counts = [
        "組合遊具數量",
        "磨石滑梯數量",
        "鞦韆數量",
        "翹翹板數量",
        "搖搖樂數量",
        "攀爬組數量",
        "戲沙坑數量",
        "擺盪船索數量",
        "其他數量",
    ]
    for p in data:
        name = (p.get("公園名稱") or "").strip()
        x, y = _f(p.get("X坐標")), _f(p.get("Y坐標"))
        key = f"{name}|{p.get('X坐標')}|{p.get('Y坐標')}"
        if key in seen:
            continue
        if x is None or y is None:
            excl.append(Exclusion(ds, key, name, "缺座標（TWD97）"))
            continue
        lon, lat = tf.transform(x, y)
        la, lo, ok = _coords(ds, key, name, lat, lon, excl)
        if not ok:
            continue
        rec = SourceRec(ds, key, name, "attraction", city="臺北市", lat=la, lon=lo, coord_note="TWD97(EPSG:3826)→WGS84")
        rec.types["park_playground"] = Attr(True, "confirmed", "臺北市公園遊具設施資料集")
        total = sum(int(_f(p.get(c)) or 0) for c in counts)
        if total > 0:
            rec.facilities["playground"] = Attr("yes", "confirmed", f"遊具數量合計 {total}")
        rec.display = {
            "equipment_counts": {c.replace("數量", ""): int(_f(p.get(c)) or 0) for c in counts},
            "district": p.get("行政區"),
            "manager": p.get("管理單位"),
        }
        _type_inference(rec)
        seen[key] = rec
        recs.append(rec)
    return recs, [], excl


def load_taichung_inclusive(raw: Path) -> Loaded:
    ds = "taichung_inclusive_playgrounds"
    recs: list[SourceRec] = []
    excl: list[Exclusion] = []
    for r in _read_csv(raw / "taichung_inclusive_playgrounds.csv", "cp950", strip_double_bom=True):
        key = (r.get("number") or "").strip()
        name = (r.get("location") or "").strip()
        if not key or not name:
            continue
        lat, lon, ok = _coords(ds, key, name, r.get("latitude"), r.get("longitude"), excl, required=True)
        if not ok:
            continue
        addr = nfkc(r.get("address") or "").strip() or None
        rec = SourceRec(ds, key, name, "attraction", address=addr, city="臺中市", lat=lat, lon=lon)
        rec.types["park_playground"] = Attr(True, "confirmed", "臺中市共融式遊戲場資料集")
        rec.facilities["playground"] = Attr("yes", "confirmed", "共融式遊戲場")
        rec.indoor = Attr("outdoor", "inferred", "共融遊戲場依資料集類型推定室外，非場勘")
        rec.display = {"district": r.get("district"), "link": r.get("link") or None}
        recs.append(rec)
    return recs, [], excl


def load_taoyuan_playgrounds(raw: Path) -> Loaded:
    ds = "taoyuan_themed_playgrounds"
    recs = []
    for r in _read_csv(raw / "taoyuan_thremed_playgrounds.csv", "utf-8"):
        name = (r.get("公園名稱") or "").strip()
        addr = nfkc(r.get("地址") or "").strip()
        addr = f"桃園市{addr}" if addr and not addr.startswith("桃園市") else addr
        rec = SourceRec(ds, name, name, "attraction", address=addr or None, city="桃園市")
        rec.types["park_playground"] = Attr(True, "confirmed", "桃園市特色遊戲場資料集")
        rec.facilities["playground"] = Attr("yes", "confirmed", "特色遊戲場")
        rec.indoor = Attr("outdoor", "inferred", "特色遊戲場依資料集類型推定室外，非場勘")
        rec.display = {"features": r.get("特色") or None, "equipment": r.get("設施") or None, "district": r.get("區域")}
        recs.append(rec)
    return recs, [], []


_VENUE_SUFFIX = re.compile(r"(\([^()]*\)|\d+號|[一二三四五六七八九十]+號)$")


def venue_name(name: str) -> str:
    """設施點位名稱去掉尾端編號／管理註記，取場域名稱。例：大安森林公園(署)→大安森林公園。"""
    t = nfkc(name).strip()
    prev = None
    while prev != t:
        prev = t
        t = _VENUE_SUFFIX.sub("", t).strip()
    return t


def load_taipei_family_toilets(raw: Path) -> Loaded:
    ds = "taipei_family_toilets"
    pts: list[FacilityPoint] = []
    excl: list[Exclusion] = []
    for r in _read_csv(raw / "taipei_family_toilets.csv", "cp950"):
        key = (r.get("公廁編號") or "").strip()
        name = (r.get("公廁名稱") or "").strip()
        lat, lon, _ = _coords(ds, key, name, r.get("緯度"), r.get("經度"), excl)
        pts.append(
            FacilityPoint(
                ds,
                key,
                "family_toilet",
                venue_name(name),
                r.get("公廁類別"),
                lat,
                lon,
                "臺北市",
                note=(
                    f"{r.get('公廁位置') or ''}；尿布臺 {r.get('尿布臺設置數量')}、兒童座椅 {r.get('兒童座椅設置數量')}"
                ),
            )
        )
    return [], pts, excl


SCHOOL = re.compile(r"(國小|國中|高中|大學|學校|國民小學|國民中學|附設實驗)")
STAFF_ONLY = re.compile(r"(僅供(本校|校內|員工|內部)|限(員工|校內|本校)|員工專用)")


def load_chiayi_nursing(raw: Path) -> Loaded:
    ds = "chiayi_city_nursing_rooms"
    pts: list[FacilityPoint] = []
    excl: list[Exclusion] = []
    for i, r in enumerate(_read_csv(raw / "chiayi_city_nursing_rooms.csv", "utf-8"), start=1):
        name = (r.get("公共場所名稱") or "").strip()
        key = f"{i}:{name}"
        note = r.get("注意事項") or ""
        if r.get("類別") == "自願設置" and (SCHOOL.search(name) or STAFF_ONLY.search(note)):
            excl.append(Exclusion(ds, key, name, "自願設置且屬校內／員工使用場所"))
            continue
        if STAFF_ONLY.search(note):
            excl.append(Exclusion(ds, key, name, "注意事項限內部人員使用"))
            continue
        lat, lon, _ = _coords(ds, key, name, r.get("緯度"), r.get("經度"), excl)
        pts.append(
            FacilityPoint(
                ds,
                key,
                "nursing_room",
                venue_name(name),
                r.get("類別"),
                lat,
                lon,
                "嘉義市",
                note=f"{r.get('開放時間') or ''} {note}".strip(),
            )
        )
    return [], pts, excl


def all_loaders(today: date) -> dict[str, Callable[[Path], Loaded]]:
    return {
        "tdx_attractions": load_tdx_attractions,
        "tdx_hotels": load_tdx_hotels,
        "taipei_attractions": load_taipei_attractions,
        "tainan_attractions": load_tainan_attractions,
        "taoyuan_attractions": load_taoyuan_attractions,
        "hsinchu_city_attractions": load_hsinchu_city_attractions,
        "tw_museums": load_tw_museums,
        "tw_leisure_agri_areas": load_leisure_agri,
        "tw_tourism_factories": load_tourism_factories,
        "tw_env_edu_sites": lambda raw: load_env_edu(raw, today),
        "taipei_parent_child_centers": load_parent_child_centers,
        "taipei_park_facility": load_taipei_park_facility,
        "taichung_inclusive_playgrounds": load_taichung_inclusive,
        "taoyuan_themed_playgrounds": load_taoyuan_playgrounds,
        "taipei_family_toilets": load_taipei_family_toilets,
        "chiayi_city_nursing_rooms": load_chiayi_nursing,
    }


__all__ = ["all_loaders", "norm_name", "venue_name", "TDX_CLASS_NAMES"]
