"""把 data/clean 的清洗結果載入 MySQL（來源追溯與下架規則）。

用法（以 migration 以外的維運身分執行；只寫入地點與來源資料表）：
    DATABASE_URL=mysql+aiomysql://... python -m etl.load_db --data ../data --mode full
連線 RDS 時另設 DB_SSL_CA（RDS CA bundle 路徑），以 TLS 連線並驗證 CA 與主機名稱。

規則：
- 每個資料集一個 import_batch（full／incremental）。只有「成功完成的完整匯入」才把本批未再出現的
  source_records 標記 removed_at；失敗、部分或增量匯入不據此判斷。
- 地點的所有有效來源紀錄都移除時，地點才 soft delete（removed_at）；仍有其他有效來源則不停用。
- 完整匯入時某資料集 0 筆：與下載／解析失敗無法區分，視為異常、不建立該資料集批次，也不據此下架。
- 內部地點 ID 不可變：既有來源紀錄已對應的地點沿用原 ID；只對全新叢集產生新的 UUIDv7。
- 重新匯入只取代 source_type=open_data 的屬性列，保留人工（manual）確認的屬性。
- 不寫入任何 Google 欄位；google_place_id 由 Place ID 配對腳本另行處理。
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import and_, bindparam, delete, select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.db.models import (
    Dataset,
    ImportBatch,
    Place,
    PlaceAgeRange,
    PlaceFacility,
    PlaceType,
    SourceRecord,
)
from app.db.session import connect_args
from app.ids import new_id

CHUNK = 500


def _now() -> datetime:
    return datetime.now(UTC)


_DATE_ONLY = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$")


def _date(v: str | None) -> date | None:
    """日期欄位；除 ISO 格式外也接受試算表另存時常見的 2026/10/16、2026/8/3。"""
    v = (v or "").strip()
    if not v:
        return None
    m = _DATE_ONLY.match(v)
    if not m:
        raise ValueError(f"日期格式無法辨識：{v!r}（請用 YYYY-MM-DD）")
    return date(int(m[1]), int(m[2]), int(m[3]))


def _source_updated(v: str | None) -> str | None:
    """來源更新時間保留原字串；純日期統一成 YYYY-MM-DD。"""
    v = (v or "").strip()
    if not v:
        return None
    d = _date(v) if _DATE_ONLY.match(v) else None
    return d.isoformat() if d else v


LICENSE_STATUSES = {"verified", "unverified"}


def _dec(v) -> Decimal | None:
    return None if v is None else Decimal(str(v)).quantize(Decimal("0.000001"))


def _license_status(r: dict[str, str]) -> str:
    v = (r["license_status"] or "").strip().lower()
    if v not in LICENSE_STATUSES:
        raise ValueError(f"{r['dataset_key']}：license_status 只能是 verified 或 unverified，目前為 {v!r}")
    return v


async def upsert_datasets(conn: AsyncConnection, manifest_path: Path) -> dict[str, uuid.UUID]:
    with manifest_path.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    existing = {r.dataset_key: r.id for r in (await conn.execute(select(Dataset.dataset_key, Dataset.id))).all()}
    out = {}
    for r in rows:
        did = existing.get(r["dataset_key"]) or new_id()
        values = dict(
            id=did,
            dataset_key=r["dataset_key"],
            title=r["title"],
            provider=r["provider"] or None,
            source_url=r["source_url"],
            license=r["license"],
            license_url=r["license_url"] or None,
            license_status=_license_status(r),
            license_checked_at=_date(r["license_checked_at"]),
            source_updated_at=_source_updated(r["source_updated_at"]),
            downloaded_at=_date(r["downloaded_at"]),
            crs=r["crs"] or None,
            role=r["role"],
            import_policy=r["import_policy"],
            notes=r["notes"] or None,
        )
        stmt = mysql_insert(Dataset).values(**values)
        upd: dict[str, Any] = {k: stmt.inserted[k] for k in values if k not in ("id", "dataset_key")}
        upd["updated_at"] = _now()
        await conn.execute(stmt.on_duplicate_key_update(**upd))
        out[r["dataset_key"]] = did
    return out


async def run(data_dir: Path, mode: str, database_url: str) -> dict:
    places = [json.loads(line) for line in (data_dir / "clean" / "places.jsonl").open(encoding="utf-8")]
    srcs = [json.loads(line) for line in (data_dir / "clean" / "source_records.jsonl").open(encoding="utf-8")]
    engine = create_async_engine(database_url, connect_args=connect_args(os.environ.get("DB_SSL_CA") or None))
    stats: dict = defaultdict(int)
    batches: dict[str, uuid.UUID] = {}
    try:
        async with engine.begin() as conn:
            ds_ids = await upsert_datasets(conn, data_dir / "manifest_complete.csv")
            used = {s["dataset_key"] for s in srcs}
            for key in used:
                bid = new_id()
                batches[key] = bid
                await conn.execute(
                    mysql_insert(ImportBatch).values(
                        id=bid, dataset_id=ds_ids[key], mode=mode, status="running", started_at=_now()
                    )
                )
        try:
            async with engine.begin() as conn:
                await _load(
                    conn, places, srcs, ds_ids, batches, stats, data_dir / "review" / "place_identity_conflicts.json"
                )
                if mode == "full":
                    await _mark_removed(conn, ds_ids, batches, stats)
                await _refresh_place_removal(conn, stats)
                for key, bid in batches.items():
                    await conn.execute(
                        update(ImportBatch)
                        .where(ImportBatch.id == bid)
                        .values(
                            status="succeeded",
                            finished_at=_now(),
                            record_count=sum(1 for s in srcs if s["dataset_key"] == key),
                            removed_count=stats.get(f"removed:{key}", 0),
                        )
                    )
        except Exception as e:
            async with engine.begin() as conn:
                for bid in batches.values():
                    await conn.execute(
                        update(ImportBatch)
                        .where(ImportBatch.id == bid)
                        .values(status="failed", finished_at=_now(), note=str(e)[:2000])
                    )
            raise
    finally:
        await engine.dispose()
    return dict(stats)


async def _load(
    conn: AsyncConnection,
    places: list[dict],
    srcs: list[dict],
    ds_ids: dict[str, uuid.UUID],
    batches: dict[str, uuid.UUID],
    stats: dict,
    report_path: Path | None = None,
) -> None:
    existing: dict[tuple[str, str], tuple[uuid.UUID, uuid.UUID | None]] = {}
    id_to_key = {v: k for k, v in ds_ids.items()}
    res = await conn.execute(
        select(SourceRecord.dataset_id, SourceRecord.source_key, SourceRecord.id, SourceRecord.place_id)
    )
    for did, sk, sid, pid in res.all():
        existing[(id_to_key.get(did, "?"), sk)] = (sid, pid)
    matched = select(Place.id).where(Place.place_id_status == "accepted", Place.google_place_id.is_not(None))
    has_gpid = set((await conn.execute(matched)).scalars().all())

    src_by_key = {(s["dataset_key"], s["source_key"]): s for s in srcs}
    rec_ids: dict[tuple[str, str], uuid.UUID] = {}
    for k in src_by_key:
        rec_ids[k] = existing[k][0] if k in existing else new_id()

    conflicts = []
    assigned: set[uuid.UUID] = set()
    place_rows, type_rows, fac_rows, place_of_rec = [], [], [], {}
    for p in places:
        members = [tuple(m) for m in p["members"]]
        olds: set[uuid.UUID] = {pid_ for m in members if m in existing and (pid_ := existing[m][1]) is not None}
        free = sorted((u for u in olds if u not in assigned), key=lambda u: (u not in has_gpid, u.bytes))
        if free:
            pid = free[0]
            if len(olds) > 1:
                conflicts.append({"type": "merged", "place_ids": [str(x) for x in olds], "members": members})
        else:
            pid = new_id()
            if olds:
                conflicts.append({"type": "split", "place_ids": [str(x) for x in olds], "members": members})
        assigned.add(pid)
        for m in members:
            place_of_rec[m] = pid
        coord_rec = rec_ids[tuple(p["coord_source"])]
        indoor = p.get("indoor")
        stay = p.get("source_stay_minutes")
        place_rows.append(
            dict(
                id=pid,
                kind=p["kind"],
                name=p["name"][:255],
                address=(p.get("address") or None) and p["address"][:512],
                city=p.get("city"),
                lat=_dec(p["lat"]),
                lon=_dec(p["lon"]),
                coord_source_record_id=coord_rec,
                primary_type=p.get("primary_type"),
                indoor=None if indoor is None else indoor["value"],
                indoor_confirmation="unknown" if indoor is None else indoor["confirmation"],
                indoor_source_type=None if indoor is None else indoor["source_type"],
                indoor_evidence_record_id=None
                if indoor is None or not indoor.get("source")
                else rec_ids.get(tuple(indoor["source"])),
                indoor_evidence_note=None if indoor is None else indoor["evidence"][:512],
                indoor_verified_at=None,
                source_stay_minutes=None if stay is None else stay["minutes"],
                source_stay_record_id=None if stay is None else rec_ids[tuple(stay["source"])],
                service_status=p.get("service_status"),
                public_access=p.get("public_access"),
            )
        )
        for t, a in p["types"].items():
            type_rows.append(
                dict(
                    place_id=pid,
                    type=t,
                    confirmation=a["confirmation"],
                    source_type=a["source_type"],
                    evidence_record_id=rec_ids.get(tuple(a["source"])),
                    evidence_note=a["evidence"][:512],
                    verified_at=None,
                )
            )
        for f, a in p["facilities"].items():
            fac_rows.append(
                dict(
                    place_id=pid,
                    facility=f,
                    status=a["value"],
                    confirmation=a["confirmation"],
                    source_type=a["source_type"],
                    evidence_record_id=rec_ids.get(tuple(a["source"])),
                    evidence_note=a["evidence"][:512],
                    verified_at=None,
                )
            )

    now = _now()
    for i in range(0, len(place_rows), CHUNK):
        chunk = place_rows[i : i + CHUNK]
        stmt = mysql_insert(Place)
        upd_p: dict[str, Any] = {c: stmt.inserted[c] for c in chunk[0] if c not in ("id", "coord_source_record_id")}
        upd_p["updated_at"] = now
        await conn.execute(
            stmt.on_duplicate_key_update(**upd_p), [{**r, "coord_source_record_id": None} for r in chunk]
        )
    stats["places_upserted"] = len(place_rows)

    rows = []
    for k, s in src_by_key.items():
        bid = batches[k[0]]
        rows.append(
            dict(
                id=rec_ids[k],
                dataset_id=ds_ids[k[0]],
                source_key=k[1][:255],
                place_id=place_of_rec.get(k),
                first_batch_id=bid,
                last_seen_batch_id=bid,
                removed_at=None,
                name=(s["name"] or "")[:255],
                address=(s.get("address") or None) and s["address"][:512],
                city=s.get("city"),
                lat=_dec(s.get("lat")),
                lon=_dec(s.get("lon")),
                coord_note=s.get("coord_note"),
                source_updated_at=(s.get("source_updated_at") or None) and str(s["source_updated_at"])[:64],
                service_status=s.get("service_status"),
                public_access=s.get("public_access"),
                display=s.get("display"),
            )
        )
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i : i + CHUNK]
        stmt = mysql_insert(SourceRecord)
        upd = {c: stmt.inserted[c] for c in chunk[0] if c not in ("id", "dataset_id", "source_key", "first_batch_id")}
        await conn.execute(stmt.on_duplicate_key_update(**upd), chunk)
    stats["source_records_upserted"] = len(rows)

    upd_stmt = (
        update(Place)
        .where(Place.id == bindparam("pid"))
        .values(coord_source_record_id=bindparam("rid"))
        .execution_options(synchronize_session=False)
    )
    await conn.execute(upd_stmt, [{"pid": r["id"], "rid": r["coord_source_record_id"]} for r in place_rows])

    pids = [r["id"] for r in place_rows]
    for i in range(0, len(pids), CHUNK):
        part = pids[i : i + CHUNK]
        for model in (PlaceType, PlaceFacility, PlaceAgeRange):
            await conn.execute(delete(model).where(and_(model.place_id.in_(part), model.source_type == "open_data")))
    manual_types = {
        (r.place_id, r.type)
        for r in (
            await conn.execute(select(PlaceType.place_id, PlaceType.type).where(PlaceType.source_type == "manual"))
        ).all()
    }
    manual_facs = {
        (r.place_id, r.facility)
        for r in (
            await conn.execute(
                select(PlaceFacility.place_id, PlaceFacility.facility).where(PlaceFacility.source_type == "manual")
            )
        ).all()
    }
    type_rows = [r for r in type_rows if (r["place_id"], r["type"]) not in manual_types]
    fac_rows = [r for r in fac_rows if (r["place_id"], r["facility"]) not in manual_facs]
    for model, rws in ((PlaceType, type_rows), (PlaceFacility, fac_rows)):
        for i in range(0, len(rws), CHUNK):
            await conn.execute(mysql_insert(model), rws[i : i + CHUNK])
    stats["place_types"] = len(type_rows)
    stats["place_facilities"] = len(fac_rows)
    stats["place_identity_conflicts"] = len(conflicts)
    if conflicts:
        env = os.environ.get("LOAD_CONFLICT_REPORT")
        out = Path(env) if env else (report_path or Path("place_identity_conflicts.json"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(conflicts, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


async def _mark_removed(
    conn: AsyncConnection, ds_ids: dict[str, uuid.UUID], batches: dict[str, uuid.UUID], stats: dict
) -> None:
    """只對本次成功完成的完整匯入資料集，標記未再出現的來源紀錄為移除。"""
    now = _now()
    for key, bid in batches.items():
        r = await conn.execute(
            update(SourceRecord)
            .where(
                and_(
                    SourceRecord.dataset_id == ds_ids[key],
                    SourceRecord.last_seen_batch_id != bid,
                    SourceRecord.removed_at.is_(None),
                )
            )
            .values(removed_at=now)
        )
        stats[f"removed:{key}"] = r.rowcount


async def _refresh_place_removal(conn: AsyncConnection, stats: dict) -> None:
    """所有有效來源紀錄都移除的地點才 soft delete；仍有有效來源者恢復。"""
    now = _now()
    active = (
        select(SourceRecord.place_id)
        .where(and_(SourceRecord.place_id.is_not(None), SourceRecord.removed_at.is_(None)))
        .distinct()
    )
    r1 = await conn.execute(
        update(Place).where(and_(Place.removed_at.is_(None), Place.id.not_in(active))).values(removed_at=now)
    )
    r2 = await conn.execute(
        update(Place).where(and_(Place.removed_at.is_not(None), Place.id.in_(active))).values(removed_at=None)
    )
    stats["places_soft_deleted"] = r1.rowcount
    stats["places_restored"] = r2.rowcount


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("../data"))
    ap.add_argument("--mode", choices=["full", "incremental"], default="full")
    a = ap.parse_args()
    url = os.environ["DATABASE_URL"]
    print(json.dumps(asyncio.run(run(a.data, a.mode, url)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
