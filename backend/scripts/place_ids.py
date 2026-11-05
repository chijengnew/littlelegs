"""Place ID 配對與更新。

子命令：
  match    以獨立來源「名稱＋地址」做 Text Search (New)；field mask = places.id,displayName,formattedAddress,location
           （含 Pro 欄位，不能按 ID-only 免費估算）。自動接受規則見 judge()；其他寫入人工審查 CSV，
           並寫明需要人工判斷的原因（只放獨立來源資料、候選 Place ID 與狀態，不寫任何 Google 內容）。
           --type 可只配對指定主要類型（例如先配親子相關類型，「其他」類稍後再配）。
  recheck  以目前規則重新判斷待審地點：符合自動接受者直接接受，其餘更新審查原因；
           --reason／--name-variants 可只重查部分列，其餘沿用原列；
           已填 decision、尚未 apply 的列保留不動；有效的對應衝突列沿用原內容、不重新搜尋，
           留待人工以 decision 處理。只寫入有效（未下架）的待審與衝突地點；審查 CSV 會改寫，原檔另存為 .bak。
  reverify 以目前規則重新驗證某段時間內「已接受」的配對（例如規則修正前接受者）：
           結果一致者保留；不一致者清除 Place ID、改為待審並寫入審查 CSV。
           驗證過的地點會更新查核時間，中途因額度停止時，以相同參數再執行即可接續。
  show     人工審查時「重新取回」某地點的候選 Google 內容，只印在終端，不寫檔。
  apply    套用審查 CSV（decision=accept/reject）。
  reset    清除指定地點的 Place ID（配錯時使用），狀態改回未配對，下次 match 會重新配對。
  refresh Place ID 逾 12 個月重新查核（只取 id）；NOT_FOUND 依原獨立來源重新搜尋；新 ID 已映射其他地點
          → mapping_conflict，暫停該地點的新候選，不自動合併、不改寫收藏。
  export   匯出已接受的 Place ID（例如本機 → 正式資料庫）。各資料庫的地點內部 ID 是匯入時各自產生的，
           因此以「資料集鍵＋來源鍵」識別地點；每列一筆有效來源紀錄，只含獨立來源名稱、Place ID 與查核時間。
  import   依來源紀錄鍵找到目標資料庫的地點並寫入 Place ID，保留原查核時間（reverify／refresh 依此判斷）。
           只寫入尚未配對（none）的地點；來源鍵對到多個地點、地點已有其他 Place ID 或已有人工結論、
           Place ID 已被其他地點使用時一律略過並列出原因，不覆寫。全部在同一交易寫入；--dry-run 只顯示結果。
           export、import 都不呼叫 Google。
  dedupe   對應衝突中「同名（忽略行政前綴）且相距 ≤1 km」的地點視為重複景點，寫入清洗流程的整併決定
           （data/review/dedup_decisions.csv）；其他列出供人工確認。不呼叫 Google；
           寫入後重跑 etl.pipeline 與 etl.load_db。

每次外部嘗試都先扣應用出站額度：每日 Google 外部請求上限，以及 Text Search Pro 每月免費額度（預設 5,000 次，
美西時間每月 1 日重置）。任一額度用完即停止，下次（隔天或下個月）從未處理的地點繼續；
重查與人工審查可能延後配對完成時間。

用法：
  python -m scripts.place_ids match --limit 200 [--city 臺北市] [--type park_playground,museum]
  python -m scripts.place_ids recheck [--reason 來源名稱包含 ...] [--name-variants]
  python -m scripts.place_ids reverify --from "2026-10-22 21:30" --to "2026-10-22 23:00"
  python -m scripts.place_ids reset --name 國立自然科學博物館之植物園 [--name ...] [<internal_place_id> ...]
  python -m scripts.place_ids show <internal_place_id>
  python -m scripts.place_ids apply ../data/review/place_id_review.csv
  python -m scripts.place_ids refresh --limit 200
  python -m scripts.place_ids export [--out ../data/place_id_export.csv]
  python -m scripts.place_ids import ../data/place_id_export.csv [--dry-run]
  python -m scripts.place_ids dedupe [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import re
import shutil
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError

from app.db.models import Dataset, Place, PlaceIdAlias, SourceRecord
from app.external.google import Deadline, GoogleError
from app.geo import haversine_m
from app.ratelimit import QuotaExceeded
from app.textnorm import ADMIN_PREFIX, CITY_PREFIX, house_number_key, name_key, nfkc
from app.timeutil import TPE
from etl.model import PRIMARY_TYPE_PRIORITY as PRIMARY_TYPES

from ._common import db, google, setup_logging

log = logging.getLogger("littlelegs.place_ids")
NEAR_M = 100.0
NEARBY_M = 1000.0
MIN_CONTAINED_CHARS = 3
REFRESH_AFTER = timedelta(days=365)
DEFAULT_REVIEW_CSV = "../data/review/place_id_review.csv"
DEFAULT_EXPORT_CSV = "../data/place_id_export.csv"
DEFAULT_DEDUP_CSV = "../data/review/dedup_decisions.csv"
DEDUP_HEADER = [
    "dataset_key",
    "source_key",
    "name",
    "address",
    "target_dataset_key",
    "target_source_key",
    "target_name",
    "target_address",
    "distance_m",
    "rule",
    "decision",
    "reason",
    "decided_by",
]
EXPORT_HEADER = ["google_place_id", "dataset_key", "source_key", "place_id_checked_at", "name"]
REVIEW_HEADER = [
    "place_id",
    "name",
    "address",
    "lat",
    "lon",
    "candidate_place_ids",
    "reason",
    "status",
    "decision",
    "chosen_place_id",
]


def now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Candidate:
    place_id: str
    same_name: bool
    distance_m: float | None
    same_house_number: bool
    contains_name: bool = False
    within_name: bool = False


_PAREN = re.compile(r"[（(]([^（）()]*)[）)]")


def name_keys(name: str) -> tuple[str, set[str]]:
    """來源名稱的比對鍵：(主鍵, 所有可視為同名的鍵)。主鍵去掉括號內容；括號內 3 字以上的別名也視為同名，
    例如「龍岡圖書館(桃園市立圖書館龍岡分館)」。"""
    base = name_key(_PAREN.sub("", name)) or name_key(name)
    keys = {base, name_key(name)}
    keys |= {k for a in _PAREN.findall(name) if len(k := name_key(a)) >= MIN_CONTAINED_CHARS}
    return base, keys


def _candidates(place, results: list[dict]) -> list[Candidate]:
    """Google 內容只在記憶體內比對：名稱（簡繁、臺台統一）、距離、門牌。"""
    (target, same_keys), house = name_keys(place.name), house_number_key(place.address)
    out = []
    for r in results:
        pid = r.get("id")
        if not isinstance(pid, str):
            continue
        loc = r.get("location") or {}
        la, lo = loc.get("latitude"), loc.get("longitude")
        d = (
            haversine_m(float(place.lat), float(place.lon), float(la), float(lo))
            if isinstance(la, (int, float)) and isinstance(lo, (int, float))
            else None
        )
        key = name_key(((r.get("displayName") or {}).get("text")) or "")
        same_house = house is not None and house == house_number_key(r.get("formattedAddress"))
        same = key in same_keys
        partial = not same and min(len(key), len(target)) >= MIN_CONTAINED_CHARS
        contains = partial and target in key
        within = partial and key in target
        out.append(Candidate(pid, same, d, same_house, contains, within))
    return out


def judge(place, results: list[dict]) -> tuple[str | None, list[str], str]:
    """回傳 (自動接受的 Place ID 或 None, 候選 ID 清單, 接受規則或需要人工判斷的原因)。

    自動接受（名稱比對已統一簡繁與臺台）：
      1. 同名且 100 m 內只有這一筆同名
      2. 同名且 1 km 內只有這一筆同名
      3. 同名且門牌號碼相同（不論距離），且只有這一筆
      4. 沒有同名候選時：Google 名稱包含來源名稱（來源名稱至少 3 個字），而且門牌相同或 100 m 內，而且只有一筆
      5. 沒有 4 的候選時：來源名稱包含 Google 名稱（例如子區域對到母場館），而且門牌相同或 100 m 內，而且只有一筆；
         該 Place ID 已是其他地點時（母場館本身也在資料庫）不接受、維持待審（見 SUB_AREA_ACCEPT）
    名稱比對忽略縣市與「國立／市立」等行政前綴，括號內容另作別名（見 name_keys）。
    各規則指向的地點必須一致；指向不同地點時交由人工判斷。
    """
    cands = _candidates(place, results)
    ids = [c.place_id for c in cands]
    if not cands:
        return None, ids, "Google 查無結果"
    same = [c for c in cands if c.same_name]
    if not same:
        return _judge_contained(place, cands, ids)

    def within(m: float) -> list[Candidate]:
        return [c for c in same if c.distance_m is not None and c.distance_m <= m]

    rules = [
        ("同名且 100 m 內唯一", within(NEAR_M)),
        ("同名且 1 km 內唯一", within(NEARBY_M)),
        ("同名且門牌相同", [c for c in same if c.same_house_number]),
    ]
    winners = {hits[0].place_id: label for label, hits in rules if len(hits) == 1}
    if len(winners) == 1:
        pid, label = next(iter(winners.items()))
        return pid, ids, f"自動接受：{label}"
    if len(winners) > 1:
        return None, ids, "多個同名，距離與門牌指向不同地點"
    if len(same) > 1:
        return None, ids, f"多個同名（{len(same)} 筆）"
    c = same[0]
    dist = "距離不明" if c.distance_m is None else "距離 >1 km"
    house = "門牌不同" if house_number_key(place.address) else "來源無門牌可比對"
    return None, ids, f"同名但{dist}，且{house}"


def _judge_contained(place, cands: list[Candidate], ids: list[str]) -> tuple[str | None, list[str], str]:
    """沒有同名候選時：先看「Google 名稱包含來源名稱」，沒有才看反方向（子區域對到母場館）。"""
    house = "門牌不同" if house_number_key(place.address) else "來源無門牌可比對"
    contained = [c for c in cands if c.contains_name]
    if not contained:
        within = [c for c in cands if c.within_name]
        if not within:
            return None, ids, f"名稱不同（Google 前 {len(cands)} 筆皆不同名）"
        ok = [c for c in within if _close(c)]
        if len(ok) == 1:
            return ok[0].place_id, ids, f"{SUB_AREA_ACCEPT}且{_how(ok[0])}，且只有一筆"
        if len(ok) > 1:
            return None, ids, f"多個來源名稱包含 Google 名稱的候選（{len(ok)} 筆）符合門牌或距離"
        return None, ids, f"來源名稱包含 Google 名稱但距離 >100 m，且{house}"
    ok = [c for c in contained if _close(c)]
    if len(ok) == 1:
        return ok[0].place_id, ids, f"自動接受：Google 名稱包含來源名稱且{_how(ok[0])}，且只有一筆"
    if len(ok) > 1:
        return None, ids, f"多個 Google 名稱包含來源名稱的候選（{len(ok)} 筆）符合門牌或距離"
    return None, ids, f"Google 名稱包含來源名稱但距離 >100 m，且{house}"


SUB_AREA_ACCEPT = "自動接受：來源名稱包含 Google 名稱"
SUB_AREA_TAKEN = "來源名稱包含 Google 名稱，但該 Place ID 已是其他地點（可能是子區域對到母場館）"


def _close(c: Candidate) -> bool:
    return c.same_house_number or (c.distance_m is not None and c.distance_m <= NEAR_M)


def _how(c: Candidate) -> str:
    return "門牌相同" if c.same_house_number else "100 m 內"


async def _mapped_elsewhere(s, gpid: str, place_id: uuid.UUID) -> bool:
    other = (await s.execute(select(Place.id).where(Place.google_place_id == gpid, Place.id != place_id))).scalar()
    alias = (await s.execute(select(PlaceIdAlias.place_id).where(PlaceIdAlias.google_place_id == gpid))).scalar()
    return other is not None or (alias is not None and alias != place_id)


async def _accept(factory, place_id: uuid.UUID, gpid: str, reason: str, *, mark_conflict: bool = True) -> str:
    """寫入 Place ID。已被其他地點使用時回傳 mapping_conflict；mark_conflict=False 時不改地點狀態。"""
    async with factory() as s, s.begin():
        if await _mapped_elsewhere(s, gpid, place_id):
            if not mark_conflict:
                return "mapping_conflict"
            await s.execute(
                update(Place).where(Place.id == place_id).values(place_id_status="mapping_conflict", updated_at=now())
            )
            return "mapping_conflict"
        cur = (await s.execute(select(Place.google_place_id).where(Place.id == place_id))).scalar()
        if cur and cur != gpid:
            s.add(PlaceIdAlias(google_place_id=cur, place_id=place_id, reason=reason))
        try:
            await s.execute(
                update(Place)
                .where(Place.id == place_id)
                .values(google_place_id=gpid, place_id_status="accepted", place_id_checked_at=now(), updated_at=now())
            )
        except IntegrityError:
            return "mapping_conflict"
    return "accepted"


async def _settle(factory, place_id: uuid.UUID, gpid: str, rule: str, tag: str) -> tuple[str, str]:
    """自動接受；回傳 (結果, 寫入審查檔的原因)。子區域規則對到已被其他地點使用的 ID 時維持待審，不算對應衝突。"""
    sub_area = rule.startswith(SUB_AREA_ACCEPT)
    r = await _accept(factory, place_id, gpid, tag, mark_conflict=not sub_area)
    if r == "accepted":
        return r, rule
    return ("review", SUB_AREA_TAKEN) if sub_area else ("conflict", CONFLICT_REASON)


def _quota_msg(e: QuotaExceeded) -> str:
    if e.window == "billing_month":
        return f"本月免費額度已用完（{e.key}，上限 {e.limit}；美西時間每月 1 日重置）"
    return f"今日外部請求額度已用完（上限 {e.limit}）"


def _review_row(p, ids: list[str], reason: str) -> list[str]:
    return [str(p.id), p.name, p.address or "", str(p.lat), str(p.lon), "|".join(ids[:5]), reason, "pending", "", ""]


CONFLICT_REASON = "候選 ID 已對應到其他地點"


def _kept_row(p, old: dict[str, str] | None, default_reason: str) -> list[str]:
    """沿用審查檔的既有列（含 decision 與候選 ID）；沒有舊列時以預設原因建立新列。"""
    if old:
        reason = old.get("reason") or old.get("rule") or default_reason
        return [reason if h == "reason" else (old.get(h) or "") for h in REVIEW_HEADER]
    return _review_row(p, [], default_reason)


def _parse_types(v: str | None) -> list[str] | None:
    if not v:
        return None
    types = [t.strip() for t in v.split(",") if t.strip()]
    bad = [t for t in types if t not in PRIMARY_TYPES]
    if bad:
        raise SystemExit(f"未知的類型：{', '.join(bad)}（可用：{', '.join(PRIMARY_TYPES)}）")
    return types


async def cmd_match(args) -> None:
    settings, eng, factory = db()
    g = google(settings, factory)
    q = select(Place).where(Place.kind == "attraction", Place.removed_at.is_(None), Place.place_id_status == "none")
    if args.city:
        q = q.where(Place.city == args.city)
    types = _parse_types(args.type)
    if types:
        q = q.where(Place.primary_type.in_(types))
    async with factory() as s:
        places = list((await s.execute(q.order_by(Place.id).limit(args.limit))).scalars())
    out = Path(args.out)
    new_file = not out.exists()
    stats = {"accepted": 0, "review": 0, "conflict": 0, "error": 0}
    with out.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(REVIEW_HEADER)
        for p in places:
            query = f"{p.name} {p.address or ''}".strip()
            try:
                res = await g.text_search(query, float(p.lat), float(p.lon), Deadline(15))
            except QuotaExceeded as e:
                log.warning("%s，停止；下次會從未處理的地點繼續", _quota_msg(e))
                break
            except GoogleError as e:
                stats["error"] += 1
                log.warning("Text Search 失敗 %s", e.kind)
                continue
            auto, ids, reason = judge(p, res)
            if auto:
                r, reason = await _settle(factory, p.id, auto, reason, "match")
                if r != "review":
                    stats[r] += 1
                if r == "accepted":
                    continue
            if reason != CONFLICT_REASON:
                stats["review"] += 1
            w.writerow(_review_row(p, ids, reason))
            async with factory() as s, s.begin():
                await s.execute(
                    update(Place)
                    .where(Place.id == p.id, Place.place_id_status == "none")
                    .values(place_id_status="pending_review", updated_at=now())
                )
    await g.aclose()
    await eng.dispose()
    print(stats)


def _taipei_to_utc(v: str) -> datetime:
    try:
        return datetime.strptime(v, "%Y-%m-%d %H:%M").replace(tzinfo=TPE).astimezone(UTC)
    except ValueError as e:
        raise SystemExit(f"時間格式須為 YYYY-MM-DD HH:MM（台北時間）：{v}") from e


async def cmd_reverify(args) -> None:
    """以目前規則重新驗證查核時間落在 [--from, --to) 的已接受配對。"""
    start, end = _taipei_to_utc(args.from_), _taipei_to_utc(args.to)
    if start >= end:
        raise SystemExit("--from 必須早於 --to")
    settings, eng, factory = db()
    g = google(settings, factory)
    async with factory() as s:
        places = list(
            (
                await s.execute(
                    select(Place)
                    .where(
                        Place.kind == "attraction",
                        Place.removed_at.is_(None),
                        Place.place_id_status == "accepted",
                        Place.google_place_id.is_not(None),
                        Place.place_id_checked_at >= start,
                        Place.place_id_checked_at < end,
                    )
                    .order_by(Place.id)
                )
            ).scalars()
        )
    print(f"待重新驗證：{len(places)} 筆")
    out = Path(args.out)
    new_file = not out.exists()
    stats = {"kept": 0, "moved_to_review": 0, "error": 0}
    with out.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(REVIEW_HEADER)
        for p in places:
            try:
                res = await g.text_search(
                    f"{p.name} {p.address or ''}".strip(), float(p.lat), float(p.lon), Deadline(15)
                )
            except QuotaExceeded as e:
                log.warning("%s，停止；以相同參數再執行即可接續", _quota_msg(e))
                break
            except GoogleError as e:
                stats["error"] += 1
                log.warning("Text Search 失敗 %s", e.kind)
                continue
            auto, ids, reason = judge(p, res)
            async with factory() as s, s.begin():
                if auto == p.google_place_id:
                    await s.execute(update(Place).where(Place.id == p.id).values(place_id_checked_at=now()))
                    stats["kept"] += 1
                    continue
                await s.execute(
                    update(Place)
                    .where(Place.id == p.id)
                    .values(
                        google_place_id=None,
                        place_id_status="pending_review",
                        place_id_checked_at=now(),
                        updated_at=now(),
                    )
                )
            if auto:
                reason = f"重新驗證指向另一筆候選（{reason.removeprefix('自動接受：')}）"
            w.writerow(_review_row(p, ids, reason))
            stats["moved_to_review"] += 1
    await g.aclose()
    await eng.dispose()
    print(stats)


def _selected(name: str, reason: str, reasons: list[str] | None, name_variants: bool) -> bool:
    """recheck 只重查符合條件的待審列：原因以 --reason 任一字串開頭，或（--name-variants）名稱有行政前綴、
    「縣市：」前綴或括號。兩者都沒指定時全部重查。"""
    if not reasons and not name_variants:
        return True
    if reasons and any(reason.startswith(r) for r in reasons):
        return True
    t = nfkc(name)
    return name_variants and (bool(ADMIN_PREFIX.match(t) or CITY_PREFIX.match(t)) or bool(_PAREN.search(t)))


async def cmd_recheck(args) -> None:
    """以目前規則重新判斷待審地點；已填 decision 的列與有效的對應衝突列保留，等使用者 apply。"""
    settings, eng, factory = db()
    g = google(settings, factory)
    out = Path(args.out)
    existing: dict[str, dict[str, str]] = {}
    if out.exists():
        with out.open(encoding="utf-8-sig", newline="") as f:
            existing = {r["place_id"]: r for r in csv.DictReader(f)}
    async with factory() as s:
        pending = list(
            (
                await s.execute(
                    select(Place)
                    .where(
                        Place.removed_at.is_(None),
                        Place.place_id_status.in_(("pending_review", "mapping_conflict")),
                    )
                    .order_by(Place.id)
                )
            ).scalars()
        )
    stats = {
        "accepted": 0,
        "review": 0,
        "kept_decided": 0,
        "kept_conflict": 0,
        "conflict": 0,
        "error": 0,
        "not_rechecked": 0,
        "not_selected": 0,
    }
    rows: list[list[str]] = []
    stopped = False
    for p in pending:
        old = existing.get(str(p.id))
        old_reason = (old.get("reason") or old.get("rule") or "") if old else ""
        if p.place_id_status == "mapping_conflict":
            rows.append(_kept_row(p, old, CONFLICT_REASON))
            stats["kept_conflict"] += 1
            continue
        if old and (old.get("decision") or "").strip():
            rows.append(_kept_row(p, old, old_reason))
            stats["kept_decided"] += 1
            continue
        if not _selected(p.name, old_reason, args.reason, args.name_variants):
            rows.append(_kept_row(p, old, old_reason))
            stats["not_selected"] += 1
            continue
        if stopped:
            rows.append(_review_row(p, (old or {}).get("candidate_place_ids", "").split("|"), old_reason))
            stats["not_rechecked"] += 1
            continue
        try:
            res = await g.text_search(f"{p.name} {p.address or ''}".strip(), float(p.lat), float(p.lon), Deadline(15))
        except QuotaExceeded as e:
            log.warning("%s，停止；其餘待審列保留原內容", _quota_msg(e))
            stopped = True
            rows.append(_review_row(p, (old or {}).get("candidate_place_ids", "").split("|"), old_reason))
            stats["not_rechecked"] += 1
            continue
        except GoogleError as e:
            stats["error"] += 1
            log.warning("Text Search 失敗 %s", e.kind)
            rows.append(_review_row(p, (old or {}).get("candidate_place_ids", "").split("|"), old_reason))
            continue
        auto, ids, reason = judge(p, res)
        if auto:
            r, reason = await _settle(factory, p.id, auto, reason, "recheck")
            if r == "accepted":
                stats["accepted"] += 1
                continue
        rows.append(_review_row(p, ids, reason))
        stats["conflict" if reason == CONFLICT_REASON else "review"] += 1
    if out.exists():
        shutil.copy2(out, out.with_name(out.name + ".bak"))
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(REVIEW_HEADER)
        w.writerows(rows)
    await g.aclose()
    await eng.dispose()
    print(stats)


async def cmd_show(args) -> None:
    settings, eng, factory = db()
    g = google(settings, factory)
    async with factory() as s:
        p = await s.get(Place, uuid.UUID(args.place_id))
    if p is None:
        raise SystemExit("找不到地點")
    print(f"獨立來源：{p.name}｜{p.address}｜{p.lat},{p.lon}")
    try:
        res = await g.text_search(f"{p.name} {p.address or ''}".strip(), float(p.lat), float(p.lon), Deadline(15))
    except QuotaExceeded as e:
        await g.aclose()
        await eng.dispose()
        raise SystemExit(_quota_msg(e)) from e
    _, _, reason = judge(p, res)
    print(f"判斷：{reason}")
    by_id = {c.place_id: c for c in _candidates(p, res)}
    shown = [
        r
        for i, r in enumerate(res)
        if i < 5 or ((c := by_id.get(str(r.get("id")))) and (c.same_name or c.contains_name or c.within_name))
    ]
    for r in shown:
        c = by_id.get(str(r.get("id")))
        marks = (
            ("同名", c and c.same_name),
            ("Google 名稱包含來源名稱", c and c.contains_name),
            ("來源名稱包含 Google 名稱", c and c.within_name),
            ("門牌相同", c and c.same_house_number),
        )
        flags = "、".join(x for x, ok in marks if ok)
        dist = "距離不明" if c is None or c.distance_m is None else f"{c.distance_m:.0f} m"
        name = (r.get("displayName") or {}).get("text")
        print(f"- {r.get('id')}｜{name}｜{r.get('formattedAddress')}｜{dist}｜{flags or '—'}")
    await g.aclose()
    await eng.dispose()


async def cmd_reset(args) -> None:
    """配錯時清除 Place ID：以內部 ID 或完整名稱指定；同名不只一筆時拒絕，避免誤清。"""
    names = args.name or []
    ids = [uuid.UUID(x) for x in args.place_id]
    if not names and not ids:
        raise SystemExit("請指定 --name 或地點內部 ID")
    _, eng, factory = db()
    error = None
    try:
        async with factory() as s, s.begin():
            targets: list[Place] = []
            for n in names:
                q = select(Place).where(Place.name == n, Place.removed_at.is_(None))
                rows = list((await s.execute(q)).scalars())
                if len(rows) != 1:
                    raise LookupError(f"名稱「{n}」符合 {len(rows)} 筆，請改用內部 ID 指定")
                targets += rows
            for i in ids:
                p = await s.get(Place, i)
                if p is None:
                    raise LookupError(f"找不到地點 {i}")
                targets.append(p)
            for p in targets:
                old = p.google_place_id or "無"
                print(f"清除：{p.name}（{p.id}）原 Place ID {old}，狀態 {p.place_id_status} → none")
                p.google_place_id = None
                p.place_id_status = "none"
                p.place_id_checked_at = None
                p.updated_at = now()
    except LookupError as e:
        error = str(e)
    finally:
        await eng.dispose()
    if error:
        raise SystemExit(error)


async def cmd_apply(args) -> None:
    _, eng, factory = db()
    stats = {"accepted": 0, "rejected": 0, "conflict": 0, "skipped": 0}
    with open(args.csv, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            dec = (r.get("decision") or "").strip().lower()
            pid = uuid.UUID(r["place_id"])
            if dec == "accept":
                gpid = (r.get("chosen_place_id") or "").strip()
                if not gpid:
                    cands = [c for c in (r.get("candidate_place_ids") or "").split("|") if c]
                    gpid = cands[0] if len(cands) == 1 else ""
                if not gpid:
                    stats["skipped"] += 1
                    continue
                res = await _accept(factory, pid, gpid, "manual_review")
                stats["accepted" if res == "accepted" else "conflict"] += 1
            elif dec == "reject":
                async with factory() as s, s.begin():
                    await s.execute(
                        update(Place).where(Place.id == pid).values(place_id_status="no_match", updated_at=now())
                    )
                stats["rejected"] += 1
            else:
                stats["skipped"] += 1
    await eng.dispose()
    print(stats)


async def cmd_refresh(args) -> None:
    settings, eng, factory = db()
    g = google(settings, factory)
    cutoff = now() - REFRESH_AFTER
    async with factory() as s:
        q = select(Place).where(
            Place.removed_at.is_(None),
            or_(
                (Place.place_id_status == "accepted")
                & or_(Place.place_id_checked_at.is_(None), Place.place_id_checked_at < cutoff),
                Place.place_id_status == "not_found",
            ),
        )
        places = list((await s.execute(q.order_by(Place.place_id_checked_at, Place.id).limit(args.limit))).scalars())
    stats = {"unchanged": 0, "updated": 0, "not_found": 0, "conflict": 0}
    for p in places:
        try:
            if p.place_id_status == "accepted" and p.google_place_id:
                try:
                    new = await g.place_id_only(p.google_place_id, Deadline(15))
                except GoogleError as e:
                    if e.kind != "not_found":
                        raise
                    new = None
                if new == p.google_place_id:
                    async with factory() as s, s.begin():
                        await s.execute(update(Place).where(Place.id == p.id).values(place_id_checked_at=now()))
                    stats["unchanged"] += 1
                    continue
                if new is not None:
                    r = await _accept(factory, p.id, new, "refresh")
                    stats["updated" if r == "accepted" else "conflict"] += 1
                    continue
            res = await g.text_search(f"{p.name} {p.address or ''}".strip(), float(p.lat), float(p.lon), Deadline(15))
            auto, _, _ = judge(p, res)
            if auto:
                r = await _accept(factory, p.id, auto, "not_found_research")
                stats["updated" if r == "accepted" else "conflict"] += 1
            else:
                async with factory() as s, s.begin():
                    await s.execute(
                        update(Place)
                        .where(Place.id == p.id)
                        .values(place_id_status="not_found", place_id_checked_at=now(), updated_at=now())
                    )
                stats["not_found"] += 1
        except QuotaExceeded as e:
            log.warning("%s，停止", _quota_msg(e))
            break
        except GoogleError as e:
            log.warning("更新失敗 %s", e.kind)
    await g.aclose()
    await eng.dispose()
    print(stats)


async def cmd_export(args) -> None:
    _, eng, factory = db()
    async with factory() as s:
        rows = (
            await s.execute(
                select(
                    Place.google_place_id,
                    Dataset.dataset_key,
                    SourceRecord.source_key,
                    Place.place_id_checked_at,
                    Place.name,
                )
                .join(SourceRecord, SourceRecord.place_id == Place.id)
                .join(Dataset, Dataset.id == SourceRecord.dataset_id)
                .where(
                    Place.kind == "attraction",
                    Place.removed_at.is_(None),
                    Place.place_id_status == "accepted",
                    Place.google_place_id.is_not(None),
                    SourceRecord.removed_at.is_(None),
                )
                .order_by(Place.google_place_id, Dataset.dataset_key, SourceRecord.source_key)
            )
        ).all()
    await eng.dispose()
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(EXPORT_HEADER)
        for gpid, ds, sk, checked, name in rows:
            w.writerow([gpid, ds, sk, checked.astimezone(UTC).isoformat() if checked else "", name])
    print({"places": len({r[0] for r in rows}), "source_records": len(rows), "out": args.out})


@dataclass(frozen=True)
class ImportTarget:
    place_id: uuid.UUID
    status: str
    google_place_id: str | None


def plan_import(
    groups: dict[str, set[tuple[str, str]]],
    targets: dict[tuple[str, str], ImportTarget],
    taken: dict[str, uuid.UUID],
) -> tuple[list[tuple[str, ImportTarget]], dict[str, str]]:
    """決定每個 Place ID 要寫入哪個地點。

    groups：Place ID → 匯出檔中的來源紀錄鍵；targets：目標資料庫有效來源紀錄鍵 → 地點；
    taken：目標資料庫已使用的 Place ID（含 alias）→ 地點。
    回傳 (要寫入的清單, 結果：Place ID → accepted／unchanged 或略過原因)。
    """
    found: dict[str, ImportTarget] = {}
    outcome: dict[str, str] = {}
    for gpid, keys in groups.items():
        hits = {targets[k] for k in keys if k in targets}
        if not hits:
            outcome[gpid] = "找不到對應的來源紀錄"
        elif len({t.place_id for t in hits}) > 1:
            outcome[gpid] = "來源紀錄對到多個地點"
        else:
            found[gpid] = next(iter(hits))
    per_place = Counter(t.place_id for t in found.values())
    todo: list[tuple[str, ImportTarget]] = []
    for gpid, t in found.items():
        user = taken.get(gpid)
        if per_place[t.place_id] > 1:
            outcome[gpid] = "多個 Place ID 對到同一地點"
        elif t.google_place_id == gpid and t.status == "accepted":
            outcome[gpid] = "unchanged"
        elif t.google_place_id is not None:
            outcome[gpid] = "地點已有其他 Place ID"
        elif t.status != "none":
            outcome[gpid] = f"地點狀態為 {t.status}，不覆寫"
        elif user is not None and user != t.place_id:
            outcome[gpid] = "Place ID 已被其他地點使用"
        else:
            outcome[gpid] = "accepted"
            todo.append((gpid, t))
    return todo, outcome


def _read_export(path: str) -> tuple[dict[str, set[tuple[str, str]]], dict[str, datetime | None], dict[str, str]]:
    groups: dict[str, set[tuple[str, str]]] = {}
    checked: dict[str, datetime | None] = {}
    names: dict[str, str] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != EXPORT_HEADER:
            raise SystemExit(f"欄位須為 {','.join(EXPORT_HEADER)}")
        for r in reader:
            gpid = r["google_place_id"]
            if not gpid or not r["dataset_key"] or not r["source_key"]:
                raise SystemExit(f"第 {reader.line_num} 行缺少 Place ID 或來源紀錄鍵")
            groups.setdefault(gpid, set()).add((r["dataset_key"], r["source_key"]))
            v = r["place_id_checked_at"]
            checked[gpid] = datetime.fromisoformat(v) if v else None
            names.setdefault(gpid, r["name"])
    return groups, checked, names


async def cmd_import(args) -> None:
    groups, checked, names = _read_export(args.csv)
    _, eng, factory = db()
    try:
        async with factory() as s, s.begin():
            rows = (
                await s.execute(
                    select(
                        Dataset.dataset_key,
                        SourceRecord.source_key,
                        Place.id,
                        Place.place_id_status,
                        Place.google_place_id,
                    )
                    .join(Dataset, Dataset.id == SourceRecord.dataset_id)
                    .join(Place, Place.id == SourceRecord.place_id)
                    .where(Place.kind == "attraction", Place.removed_at.is_(None), SourceRecord.removed_at.is_(None))
                )
            ).all()
            targets = {(ds, sk): ImportTarget(pid, st, gp) for ds, sk, pid, st, gp in rows}
            taken: dict[str, uuid.UUID] = {
                gp: pid
                for gp, pid in (
                    await s.execute(select(Place.google_place_id, Place.id).where(Place.google_place_id.is_not(None)))
                ).all()
                if gp is not None
            }
            for gp, pid in (await s.execute(select(PlaceIdAlias.google_place_id, PlaceIdAlias.place_id))).all():
                taken.setdefault(gp, pid)
            todo, outcome = plan_import(groups, targets, taken)
            if not args.dry_run:
                for gpid, t in todo:
                    res = await s.execute(
                        update(Place)
                        .where(Place.id == t.place_id, Place.place_id_status == "none", Place.google_place_id.is_(None))
                        .values(
                            google_place_id=gpid,
                            place_id_status="accepted",
                            place_id_checked_at=checked[gpid] or now(),
                            updated_at=now(),
                        )
                    )
                    if res.rowcount != 1:  # type: ignore[attr-defined]
                        raise RuntimeError(f"地點 {t.place_id} 在匯入期間被修改，整筆回滾")
    finally:
        await eng.dispose()
    for gpid, why in sorted(outcome.items(), key=lambda x: x[1]):
        if why not in ("accepted", "unchanged"):
            print(f"略過：{names[gpid]}（{gpid}）— {why}")
    stats = Counter("略過" if v not in ("accepted", "unchanged") else v for v in outcome.values())
    print({**stats, "dry_run": args.dry_run})


@dataclass(frozen=True)
class DedupPlace:
    place_id: uuid.UUID
    name: str
    lat: float
    lon: float
    members: tuple[tuple[str, str, str, str], ...]


def plan_dedupe(
    pairs: list[tuple[DedupPlace, DedupPlace]], today: str
) -> tuple[list[list[str]], list[tuple[DedupPlace, DedupPlace, float]]]:
    """對應衝突的地點（a）與已持有該 Place ID 的地點（b）：同名（比對鍵含括號別名）且相距 ≤1 km 視為同一地點，
    為 a 的每筆來源紀錄寫一列 accept（併入 b）；其他列入人工確認。回傳 (整併決定列, 人工確認清單)。"""
    rows: list[list[str]] = []
    manual: list[tuple[DedupPlace, DedupPlace, float]] = []
    for a, b in pairs:
        d = haversine_m(a.lat, a.lon, b.lat, b.lon)
        if not (b.members and a.members and d <= NEARBY_M and name_keys(a.name)[1] & name_keys(b.name)[1]):
            manual.append((a, b, d))
            continue
        t = b.members[0]
        for m in a.members:
            rows.append(
                [
                    *m,
                    *t,
                    f"{d:.1f}",
                    "Google Place ID 相同",
                    "accept",
                    "名稱相同（忽略行政前綴）且距離 ≤1 km，Google 配對到同一 Place ID",
                    f"規則判定（{today}）",
                ]
            )
    return rows, manual


async def cmd_dedupe(args) -> None:
    """把「對應衝突」中其實是同一地點的重複景點寫入清洗流程的整併決定（dedup_decisions.csv），不呼叫 Google。
    重跑 etl.pipeline 與 etl.load_db 後，重複的地點併入已有 Place ID 的地點。"""
    cands: dict[str, list[str]] = {}
    with open(args.review, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            cands[r["place_id"]] = [c for c in (r.get("candidate_place_ids") or "").split("|") if c]
    _, eng, factory = db()

    async def load(s, p: Place) -> DedupPlace:
        q = (
            select(Dataset.dataset_key, SourceRecord.source_key, SourceRecord.name, SourceRecord.address)
            .join(Dataset, Dataset.id == SourceRecord.dataset_id)
            .where(SourceRecord.place_id == p.id, SourceRecord.removed_at.is_(None))
            .order_by(SourceRecord.lat.is_(None), Dataset.dataset_key, SourceRecord.source_key)
        )
        members = tuple((ds, sk, n or "", a or "") for ds, sk, n, a in (await s.execute(q)).all())
        return DedupPlace(p.id, p.name, float(p.lat), float(p.lon), members)

    pairs: list[tuple[DedupPlace, DedupPlace]] = []
    no_owner = 0
    async with factory() as s:
        conflicts = (
            await s.execute(
                select(Place)
                .where(Place.removed_at.is_(None), Place.place_id_status == "mapping_conflict")
                .order_by(Place.id)
            )
        ).scalars()
        for p in list(conflicts):
            owner = None
            for gpid in cands.get(str(p.id), []):
                q = select(Place).where(Place.google_place_id == gpid, Place.id != p.id, Place.removed_at.is_(None))
                owner = (await s.execute(q)).scalar()
                if owner is not None:
                    break
            if owner is None:
                no_owner += 1
                continue
            pairs.append((await load(s, p), await load(s, owner)))
    await eng.dispose()

    out = Path(args.out)
    done: set[tuple[str, str]] = set()
    if out.exists():
        with out.open(encoding="utf-8-sig", newline="") as f:
            done = {(r["dataset_key"], r["source_key"]) for r in csv.DictReader(f)}
    rows, manual = plan_dedupe(pairs, datetime.now(TPE).date().isoformat())
    new = [r for r in rows if (r[0], r[1]) not in done]
    if not args.dry_run and new:
        write_header = not out.exists()
        with out.open("a", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(DEDUP_HEADER)
            w.writerows(new)
    for a, b, d in manual:
        print(f"需人工確認：{a.name}（{a.place_id}）↔ 已配對 {b.name}（{b.place_id}），相距 {d:.0f} m")
    merged = len({(r[4], r[5]) for r in rows})
    print(
        {
            "pairs": len(pairs),
            "merge": merged,
            "rows_new": len(new),
            "manual": len(manual),
            "no_owner": no_owner,
            "dry_run": args.dry_run,
        }
    )


def main() -> None:
    setup_logging()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("match")
    m.add_argument("--limit", type=int, default=100)
    m.add_argument("--city")
    m.add_argument("--type", help=f"只配對這些主要類型，逗號分隔：{','.join(PRIMARY_TYPES)}")
    m.add_argument("--out", default=DEFAULT_REVIEW_CSV)
    rc = sub.add_parser("recheck")
    rc.add_argument("--out", default=DEFAULT_REVIEW_CSV)
    rc.add_argument("--reason", action="append", help="只重查審查原因以此開頭的列，可重複指定")
    rc.add_argument("--name-variants", action="store_true", help="另外重查名稱有行政前綴、縣市冒號前綴或括號的列")
    rv = sub.add_parser("reverify")
    rv.add_argument("--from", dest="from_", required=True, help="台北時間，例如 2026-10-22 21:30")
    rv.add_argument("--to", required=True, help="台北時間（不含），例如 2026-10-22 23:00")
    rv.add_argument("--out", default=DEFAULT_REVIEW_CSV)
    sh = sub.add_parser("show")
    sh.add_argument("place_id")
    a = sub.add_parser("apply")
    a.add_argument("csv")
    rs = sub.add_parser("reset")
    rs.add_argument("--name", action="append", help="地點完整名稱，可重複指定")
    rs.add_argument("place_id", nargs="*", help="地點內部 ID")
    r = sub.add_parser("refresh")
    r.add_argument("--limit", type=int, default=100)
    ex = sub.add_parser("export")
    ex.add_argument("--out", default=DEFAULT_EXPORT_CSV)
    im = sub.add_parser("import")
    im.add_argument("csv")
    im.add_argument("--dry-run", action="store_true", help="只顯示結果，不寫入資料庫")
    dd = sub.add_parser("dedupe")
    dd.add_argument("--review", default=DEFAULT_REVIEW_CSV)
    dd.add_argument("--out", default=DEFAULT_DEDUP_CSV)
    dd.add_argument("--dry-run", action="store_true", help="只顯示結果，不寫入整併決定")
    args = ap.parse_args()
    cmds = {
        "match": cmd_match,
        "recheck": cmd_recheck,
        "reverify": cmd_reverify,
        "show": cmd_show,
        "apply": cmd_apply,
        "reset": cmd_reset,
        "refresh": cmd_refresh,
        "export": cmd_export,
        "import": cmd_import,
        "dedupe": cmd_dedupe,
    }
    asyncio.run(cmds[args.cmd](args))


if __name__ == "__main__":
    main()
