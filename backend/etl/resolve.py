"""跨資料集實體整併（去重）與設施點位掛載。

保守規則（不捏造高信心）：
- 自動合併：正規化名稱（NFKC＋去空白標點＋臺/台）完全相同，且
  (a) 兩者皆有座標、距離 ≤ 300 m，或 (b) 正規化地址相同。
- 名稱互相包含且距離 ≤ 100 m、或名稱包含且地址相同 → 進人工審查佇列，未審前不合併。
- 無座標紀錄只能併入有座標地點；無法唯一配對者排除。
- 設施點位只依「場域名稱相同＋同縣市」掛載；距離只作防呆（≤1 km），不以距離推定。
- 人工審查決定（data/review/dedup_decisions.csv）優先於自動規則。
- 名稱、座標取優先資料集（錨點），名稱去掉底線；地址取各來源中最完整者（有門牌 > 有路名 > 只到行政區），原文不改寫。
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from app.geo import haversine_m
from app.textnorm import CITY_PREFIX, house_number_key, norm_address
from app.textnorm import name_key as _name_key

from .classify import category_types, name_types
from .model import PRIMARY_TYPE_PRIORITY, TYPE_INDOOR, Attr, Exclusion, FacilityPoint, SourceRec

DATASET_PRIORITY = [
    "tdx_attractions",
    "tdx_hotels",
    "tw_museums",
    "taipei_attractions",
    "tainan_attractions",
    "taoyuan_attractions",
    "taipei_park_facility",
    "taichung_inclusive_playgrounds",
    "tw_leisure_agri_areas",
    "tw_tourism_factories",
    "tw_env_edu_sites",
    "taipei_parent_child_centers",
    "taoyuan_themed_playgrounds",
    "hsinchu_city_attractions",
]
AUTO_DIST_M = 300.0
REVIEW_DIST_M = 100.0
FACILITY_SANITY_M = 1000.0
INTRA_DEDUP = {"tdx_attractions": 50.0}


def ll(rec) -> tuple[float, float]:
    """取座標；只在已確認有座標的紀錄上呼叫（缺座標紀錄不進格網、不參與距離比對）。"""
    assert rec.lat is not None and rec.lon is not None
    return rec.lat, rec.lon


def _prefixed_twin(r: SourceRec, c: Cluster, d: float) -> bool:
    """同一資料集內「加了縣市前綴」的重複列（例如「彰化：緞帶王觀光工廠」與「緞帶王觀光工廠」）：
    一邊有前綴、一邊沒有，名稱去前綴後相同，且距離 ≤300 m 或門牌相同時視為同一地點。"""
    twins = [m for m in c.members if m.dataset_key == r.dataset_key and name_key(m.name) == name_key(r.name)]
    r_prefixed = CITY_PREFIX.match(r.name) is not None
    twins = [m for m in twins if (CITY_PREFIX.match(m.name) is not None) != r_prefixed]
    if not twins:
        return False
    h = house_number_key(r.address)
    return d <= AUTO_DIST_M or (h is not None and any(house_number_key(m.address) == h for m in twins))


def name_key(name: str) -> str:
    """去重用名稱鍵：簡繁、臺台、全半形與標點皆統一。"""
    return _name_key(name)


def _prio(ds: str) -> int:
    return DATASET_PRIORITY.index(ds) if ds in DATASET_PRIORITY else len(DATASET_PRIORITY)


@dataclass
class Cluster:
    kind: str
    members: list[SourceRec] = field(default_factory=list)
    attached_points: list[FacilityPoint] = field(default_factory=list)

    @property
    def anchor(self) -> SourceRec:
        with_coords = [m for m in self.members if m.lat is not None]
        return sorted(with_coords or self.members, key=lambda m: _prio(m.dataset_key))[0]

    def name_keys(self) -> set[str]:
        return {name_key(m.name) for m in self.members}

    def addr_keys(self) -> set[str]:
        return {norm_address(m.address) for m in self.members if m.address}

    def cities(self) -> set[str]:
        return {(m.city or "").replace("台", "臺") for m in self.members if m.city}


@dataclass
class ReviewItem:
    dataset_key: str
    source_key: str
    name: str
    address: str | None
    target_dataset_key: str
    target_source_key: str
    target_name: str
    target_address: str | None
    distance_m: float | None
    rule: str


class _Grid:
    def __init__(self) -> None:
        self.cells: dict[tuple[int, int], list[Cluster]] = defaultdict(list)

    @staticmethod
    def cell(lat: float, lon: float) -> tuple[int, int]:
        return int(lat * 100), int(lon * 100)

    def add(self, c: Cluster) -> None:
        a = c.anchor
        if a.lat is not None:
            self.cells[self.cell(*ll(a))].append(c)

    def near(self, lat: float, lon: float) -> list[Cluster]:
        ci, cj = self.cell(lat, lon)
        out: list[Cluster] = []
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                out.extend(self.cells.get((ci + di, cj + dj), []))
        return out


def load_decisions(path: Path) -> dict[tuple[str, str], tuple[str, str, str]]:
    """(dataset, source_key) → (decision, target_dataset, target_source_key)"""
    if not path.exists():
        return {}
    out: dict[tuple[str, str], tuple[str, str, str]] = {}
    with path.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            d = (r.get("decision") or "").strip().lower()
            key = (r["dataset_key"], r["source_key"])
            if d == "accept" or (d == "reject" and out.get(key, ("",))[0] != "accept"):
                out[key] = (d, r["target_dataset_key"], r["target_source_key"])
    return out


def load_rejections(path: Path) -> dict[tuple[str, str], set[tuple[str, str]]]:
    """(dataset, source_key) → 人工決定不合併的所有目標。同一來源紀錄可對多個目標各有一列 reject；
    load_decisions 每筆來源只留最後一列，因此另外收集，避免先前拒絕的目標又回到審查清單。"""
    out: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    if not path.exists():
        return out
    with path.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if (r.get("decision") or "").strip().lower() == "reject":
                out[(r["dataset_key"], r["source_key"])].add((r["target_dataset_key"], r["target_source_key"]))
    return out


def resolve(
    records: list[SourceRec],
    points: list[FacilityPoint],
    decisions: dict,
    rejections: dict[tuple[str, str], set[tuple[str, str]]] | None = None,
) -> tuple[list[Cluster], list[ReviewItem], list[Exclusion], list[tuple[FacilityPoint, str]]]:
    reviews: list[ReviewItem] = []
    excl: list[Exclusion] = []
    unattached: list[tuple[FacilityPoint, str]] = []

    ordered = sorted(records, key=lambda r: (r.kind, _prio(r.dataset_key)))
    clusters: list[Cluster] = []
    grids = {"attraction": _Grid(), "lodging": _Grid()}
    by_member: dict[tuple[str, str], Cluster] = {}
    by_name: dict[tuple[str, str], list[Cluster]] = defaultdict(list)

    def register(c: Cluster, r: SourceRec) -> None:
        by_member[(r.dataset_key, r.source_key)] = c
        lst = by_name[(c.kind, name_key(r.name))]
        if not any(x is c for x in lst):
            lst.append(c)

    def new_cluster(r: SourceRec) -> None:
        c = Cluster(kind=r.kind, members=[r])
        clusters.append(c)
        grids[r.kind].add(c)
        register(c, r)

    def add_to(c: Cluster, r: SourceRec) -> None:
        c.members.append(r)
        register(c, r)

    deferred_no_coord: list[SourceRec] = []
    for r in ordered:
        if r.lat is None:
            deferred_no_coord.append(r)
            continue
        dec = decisions.get((r.dataset_key, r.source_key))
        if dec and dec[0] == "accept" and (dec[1], dec[2]) in by_member:
            add_to(by_member[(dec[1], dec[2])], r)
            continue
        rejected = set((rejections or {}).get((r.dataset_key, r.source_key), ()))
        if dec and dec[0] == "reject":
            rejected.add((dec[1], dec[2]))
        nk, ak = name_key(r.name), norm_address(r.address) if r.address else None
        auto: list[tuple[float, Cluster]] = []
        maybe: list[tuple[float, Cluster, str]] = []
        rlat, rlon = ll(r)
        for c in grids[r.kind].near(rlat, rlon):
            a = c.anchor
            if rejected and any((m.dataset_key, m.source_key) in rejected for m in c.members):
                continue
            d = haversine_m(rlat, rlon, *ll(a))
            if any(m.dataset_key == r.dataset_key for m in c.members):
                lim = INTRA_DEDUP.get(r.dataset_key)
                if (lim is not None and nk in c.name_keys() and d <= lim) or _prefixed_twin(r, c, d):
                    auto.append((d, c))
                continue
            if nk in c.name_keys() and (d <= AUTO_DIST_M or (ak and ak in c.addr_keys())):
                auto.append((d, c))
            elif d <= REVIEW_DIST_M and len(nk) >= 3 and any(nk in k or k in nk for k in c.name_keys() if len(k) >= 3):
                maybe.append((d, c, "名稱互相包含且距離 ≤100 m"))
        if not auto and ak:
            for c in by_name.get((r.kind, nk), []):
                d = haversine_m(rlat, rlon, *ll(c.anchor))
                same_ds = any(m.dataset_key == r.dataset_key for m in c.members)
                if (ak in c.addr_keys() and not same_ds) or (same_ds and _prefixed_twin(r, c, d)):
                    auto.append((d, c))
        if len(auto) == 1:
            add_to(auto[0][1], r)
            continue
        if len(auto) > 1:
            auto.sort(key=lambda t: t[0])
            a = auto[0][1].anchor
            reviews.append(
                ReviewItem(
                    r.dataset_key,
                    r.source_key,
                    r.name,
                    r.address,
                    a.dataset_key,
                    a.source_key,
                    a.name,
                    a.address,
                    round(auto[0][0], 1),
                    "多個同名地點皆符合，需人工擇一",
                )
            )
            new_cluster(r)
            continue
        for d, c, rule in sorted(maybe, key=lambda t: t[0])[:1]:
            a = c.anchor
            reviews.append(
                ReviewItem(
                    r.dataset_key,
                    r.source_key,
                    r.name,
                    r.address,
                    a.dataset_key,
                    a.source_key,
                    a.name,
                    a.address,
                    round(d, 1),
                    rule,
                )
            )
        new_cluster(r)

    for (ds, sk), (d, tds, tsk) in decisions.items():
        src, dst = by_member.get((ds, sk)), by_member.get((tds, tsk))
        if d != "accept" or src is None or dst is None or src is dst or src.kind != dst.kind:
            continue
        for m in src.members:
            add_to(dst, m)
            lst = by_name[(src.kind, name_key(m.name))]
            lst[:] = [x for x in lst if x is not src]
        clusters[:] = [x for x in clusters if x is not src]

    for r in deferred_no_coord:
        dec = decisions.get((r.dataset_key, r.source_key))
        if dec and dec[0] == "accept" and (dec[1], dec[2]) in by_member:
            add_to(by_member[(dec[1], dec[2])], r)
            continue
        if dec and dec[0] == "reject":
            excl.append(Exclusion(r.dataset_key, r.source_key, r.name, "人工審查決定不合併；無座標不可獨立入池"))
            continue
        nk = name_key(r.name)
        ak = norm_address(r.address) if r.address else None
        city = (r.city or "").replace("台", "臺")
        same_name = [c for c in by_name.get((r.kind, nk), []) if not city or not c.cities() or city in c.cities()]
        if len(same_name) == 1:
            add_to(same_name[0], r)
            continue
        if len(same_name) > 1 and ak:
            addr_hit = [c for c in same_name if ak in c.addr_keys()]
            if len(addr_hit) == 1:
                add_to(addr_hit[0], r)
                continue
        cand = []
        if ak:
            for c in clusters:
                if (
                    c.kind == r.kind
                    and ak in c.addr_keys()
                    and any(nk in k or k in nk for k in c.name_keys() if len(k) >= 3)
                ):
                    cand.append(c)
        if cand:
            a = cand[0].anchor
            reviews.append(
                ReviewItem(
                    r.dataset_key,
                    r.source_key,
                    r.name,
                    r.address,
                    a.dataset_key,
                    a.source_key,
                    a.name,
                    a.address,
                    None,
                    "無座標：名稱包含且地址相同，需人工確認",
                )
            )
            excl.append(Exclusion(r.dataset_key, r.source_key, r.name, "無座標，待人工確認配對（未確認前不入池）"))
        else:
            reason = "無座標且無法唯一配對到有座標地點（不人工補座標）"
            if len(same_name) > 1:
                reason = "無座標且同名地點不只一處，無法確認同一實體"
            excl.append(Exclusion(r.dataset_key, r.source_key, r.name, reason))

    att_by_name: dict[str, list[Cluster]] = defaultdict(list)
    for c in clusters:
        if c.kind != "attraction":
            continue
        for k in c.name_keys():
            att_by_name[k].append(c)
    for p in points:
        k = name_key(p.venue_name)
        hits = [c for c in att_by_name.get(k, []) if not p.city or p.city in c.cities()]
        if p.lat is not None and p.lon is not None:
            plat, plon = p.lat, p.lon
            hits = [
                c for c in hits if c.anchor.lat is None or haversine_m(plat, plon, *ll(c.anchor)) <= FACILITY_SANITY_M
            ]
        uniq = list({id(c): c for c in hits}.values())
        if len(uniq) == 1:
            uniq[0].attached_points.append(p)
        elif len(uniq) > 1:
            unattached.append((p, "同名場域不只一處，無法確認"))
        else:
            unattached.append((p, "找不到名稱相同的地點；不以距離推定"))
    return clusters, reviews, excl, unattached


@dataclass
class MergedPlace:
    kind: str
    name: str
    address: str | None
    city: str | None
    lat: float
    lon: float
    coord_dataset: str
    coord_source_key: str
    types: dict[str, Attr]
    primary_type: str | None
    indoor: Attr | None
    facilities: dict[str, tuple[Attr, str, str]]
    stay: tuple[int, str, str] | None
    stay_note: str | None
    service_status: int | None
    public_access: bool | None
    members: list[SourceRec]
    type_sources: dict[str, tuple[str, str]]
    indoor_source: tuple[str, str] | None


def round_stay(v: int) -> int | None:
    if v <= 0:
        return None
    r = (v + 7) // 15 * 15
    return max(15, min(360, r))


_ADMIN_ONLY = re.compile(r"^(\D{1,4}?[縣市])?(\D{1,4}?[鄉鎮市區])?(\D{1,4}?[村里])?$")


def address_level(addr: str | None) -> int:
    """地址完整度：3 有門牌號碼、2 有路名或地標但無門牌、1 只到行政區（例如「臺北市中正區」）、0 無地址。"""
    if not addr or not addr.strip():
        return 0
    if house_number_key(addr):
        return 3
    return 1 if _ADMIN_ONLY.match(norm_address(addr)) else 2


def best_address(c: Cluster) -> str | None:
    """取各來源中最完整的地址（原文不改寫）；同等完整時依錨點、資料集優先序。"""
    a = c.anchor
    ordered = [a, *sorted((m for m in c.members if m is not a), key=lambda m: _prio(m.dataset_key))]
    return max((m.address for m in ordered if m.address), key=address_level, default=None)


def tidy_name(name: str) -> str:
    """去掉「縣市簡稱＋冒號」前綴（例如「台南：TJCOS台鉅美妝觀光工廠」）與名稱中的底線
    （例如「北門_承恩門」→「北門承恩門」）；後段已包含前段時只留後段，避免「大稻埕碼頭_大稻埕碼頭貨櫃市集」重複。
    來源紀錄仍保存原文。"""
    name = CITY_PREFIX.sub("", name) or name
    parts = [p.strip() for p in re.split(r"[_＿ˍ]+", name) if p.strip()]
    kept = [p for i, p in enumerate(parts) if not (i + 1 < len(parts) and parts[i + 1].startswith(p))]
    return "".join(kept) or name


def display_name(c: Cluster) -> str:
    """顯示名稱取錨點來源的名稱；其他來源有同名寫法時，優先採用沒有縣市前綴、使用正體「臺」者，
    再去掉底線（tidy_name）。不做其他改寫。"""
    a = c.anchor
    same = [m.name for m in c.members if m.name and name_key(m.name) == name_key(a.name)]
    if not same:
        return tidy_name(a.name)
    return tidy_name(min(same, key=lambda n: (CITY_PREFIX.match(n) is not None, n.count("台"), same.index(n))))


def load_name_overrides(path: Path) -> dict[tuple[str, str], str]:
    """人工指定的顯示名稱：(dataset, source_key) → 名稱（review/name_overrides.csv）。
    用於來源名稱已過時（例如店家改名、重新開幕）且經人工確認的情形；來源紀錄仍保存原文。"""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig") as f:
        return {(r["dataset_key"], r["source_key"]): r["name"].strip() for r in csv.DictReader(f) if r["name"].strip()}


def merge(c: Cluster, names: dict[tuple[str, str], str] | None = None) -> MergedPlace | None:
    a = c.anchor
    if a.lat is None:
        return None
    types: dict[str, Attr] = {}
    type_src: dict[str, tuple[str, str]] = {}
    manual = [n for m in c.members if (n := (names or {}).get((m.dataset_key, m.source_key)))]
    name = manual[0] if manual else display_name(c)
    for m in sorted(c.members, key=lambda m: _prio(m.dataset_key)):
        own = {**category_types(m), **m.types} if c.kind == "attraction" else m.types
        for t, attr in own.items():
            if t not in types or (types[t].confirmation != "confirmed" and attr.confirmation == "confirmed"):
                types[t] = attr
                type_src[t] = (m.dataset_key, m.source_key)
    if c.kind == "attraction":
        for t, attr in name_types(name).items():
            if t not in types:
                types[t] = attr
                type_src[t] = (a.dataset_key, a.source_key)
    if c.kind == "attraction" and not types:
        types["other"] = Attr(True, "confirmed", "無更具體類型時歸為其他景點")
        type_src["other"] = (a.dataset_key, a.source_key)
    primary = next((t for t in PRIMARY_TYPE_PRIORITY if t in types), None) if c.kind == "attraction" else None

    indoor = None
    indoor_src = None
    confirmed = [(m, m.indoor) for m in c.members if m.indoor and m.indoor.confirmation == "confirmed"]
    inferred = [(m, m.indoor) for m in c.members if m.indoor and m.indoor.confirmation == "inferred"]
    if confirmed:
        vals = {x.value for _, x in confirmed}
        if len(vals) == 1:
            indoor, indoor_src = confirmed[0][1], (confirmed[0][0].dataset_key, confirmed[0][0].source_key)
    elif primary in TYPE_INDOOR:
        indoor = Attr(TYPE_INDOOR[primary], "inferred", f"依主要類型 {primary} 推定，非場勘")
        indoor_src = type_src[primary]
    elif inferred and len({x.value for _, x in inferred}) == 1:
        indoor, indoor_src = inferred[0][1], (inferred[0][0].dataset_key, inferred[0][0].source_key)

    facilities: dict[str, tuple[Attr, str, str]] = {}
    per: dict[str, list[tuple[Attr, str, str]]] = defaultdict(list)
    for m in c.members:
        for f, attr in m.facilities.items():
            per[f].append((attr, m.dataset_key, m.source_key))
    for p in c.attached_points:
        per[p.facility].append(
            (
                Attr("yes", "confirmed", f"獨立設施點位「{p.venue_name}」（{p.category or ''}）{p.note or ''}"),
                p.dataset_key,
                p.source_key,
            )
        )
    for f, items in per.items():
        vals = {x[0].value for x in items if x[0].confirmation == "confirmed"}
        if vals == {"yes"}:
            facilities[f] = next(x for x in items if x[0].value == "yes")
        elif vals == {"no"}:
            facilities[f] = next(x for x in items if x[0].value == "no")
        elif "yes" in vals and "no" in vals:
            facilities[f] = (Attr("unknown", "unknown", "來源記載互相矛盾"), items[0][1], items[0][2])
        else:
            facilities[f] = (Attr("unknown", "unknown", items[0][0].evidence), items[0][1], items[0][2])

    stays: list[tuple[int, str, str]] = [
        (m.stay_minutes_raw, m.dataset_key, m.source_key) for m in c.members if m.stay_minutes_raw
    ]
    stay = None
    note = None
    rounded = {round_stay(s[0]) for s in stays}
    if len(stays) >= 1 and len({s[0] for s in stays}) == 1 and None not in rounded:
        rs = round_stay(stays[0][0])
        assert rs is not None
        stay = (rs, stays[0][1], stays[0][2])
    elif len(stays) > 1:
        note = "多個來源建議停留時間不一致，不採用"

    statuses = [m.service_status for m in c.members if m.service_status is not None]
    status = 3 if 3 in statuses else (statuses[0] if statuses else None)
    pa = [m.public_access for m in c.members if m.public_access is not None]
    public = (False if False in pa else True) if pa else None
    return MergedPlace(
        c.kind,
        name,
        best_address(c),
        a.city or next((m.city for m in c.members if m.city), None),
        *ll(a),
        a.dataset_key,
        a.source_key,
        types,
        primary,
        indoor,
        facilities,
        stay,
        note,
        status,
        public,
        c.members,
        type_src,
        indoor_src,
    )
