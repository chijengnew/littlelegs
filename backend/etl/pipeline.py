"""清洗管線入口：讀取原始資料 → 清洗 → 跨資料集整併 → 輸出 data/clean 與 data/review。

用法：
    python -m etl.pipeline --raw ../data/raw --out ../data --today 2026-10-20

輸出（皆只含獨立來源欄位，不含任何 Google 內容）：
    clean/places.jsonl           整併後地點（含屬性與證據）
    clean/source_records.jsonl   各來源紀錄（供 source_records 表與追溯）
    clean/summary.json           統計
    review/exclusions.csv        排除紀錄與原因
    review/dedup_review.csv      待人工確認的整併（填 decision=accept/reject 後另存為 dedup_decisions.csv 再重跑）
    review/facility_unattached.csv 未掛載的獨立設施點位

人工輸入（重跑時讀入）：
    review/dedup_decisions.csv   整併決定（accept 併入目標／reject 不合併；同一來源紀錄可有多列）
    review/name_overrides.csv    人工指定的顯示名稱（dataset_key, source_key, name, reason, decided_by）
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .model import Exclusion, FacilityPoint, SourceRec
from .resolve import load_decisions, load_name_overrides, load_rejections, merge, resolve
from .sources import all_loaders


def read_manifest(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig") as f:
        return {r["dataset_key"]: r for r in csv.DictReader(f)}


def run(raw: Path, out: Path, today: date) -> dict:
    manifest = read_manifest(out / "manifest_complete.csv")
    loaders = all_loaders(today)
    records: list[SourceRec] = []
    points: list[FacilityPoint] = []
    exclusions: list[Exclusion] = []
    per_ds: Counter[str] = Counter()
    for key, loader in loaders.items():
        mrow = manifest.get(key)
        if mrow is None:
            raise SystemExit(f"manifest 缺少資料集 {key}；匯入前必須補齊授權、來源網址與更新時間")
        if mrow["import_policy"] == "excluded":
            continue
        recs, pts, excl = loader(raw)
        records += recs
        points += pts
        exclusions += excl
        per_ds[key] = len(recs) + len(pts)
    exclusions.append(
        Exclusion("tw_family_activities", "*", "藝文活動（整個資料集）", "初版不收錄有日期場次的活動資料")
    )

    decisions = load_decisions(out / "review" / "dedup_decisions.csv")
    rejections = load_rejections(out / "review" / "dedup_decisions.csv")
    clusters, reviews, excl2, unattached = resolve(records, points, decisions, rejections)
    exclusions += excl2

    names = load_name_overrides(out / "review" / "name_overrides.csv")
    places = []
    for c in clusters:
        mp = merge(c, names)
        if mp is None:
            continue
        places.append(mp)

    clean = out / "clean"
    review = out / "review"
    clean.mkdir(parents=True, exist_ok=True)
    review.mkdir(parents=True, exist_ok=True)

    with (clean / "places.jsonl").open("w", encoding="utf-8") as f:
        for p in places:
            f.write(
                json.dumps(
                    {
                        "kind": p.kind,
                        "name": p.name,
                        "address": p.address,
                        "city": p.city,
                        "lat": p.lat,
                        "lon": p.lon,
                        "coord_source": [p.coord_dataset, p.coord_source_key],
                        "types": {t: {**asdict(a), "source": p.type_sources[t]} for t, a in p.types.items()},
                        "primary_type": p.primary_type,
                        "indoor": None if p.indoor is None else {**asdict(p.indoor), "source": p.indoor_source},
                        "facilities": {
                            f_: {**asdict(a), "source": [ds, sk]} for f_, (a, ds, sk) in p.facilities.items()
                        },
                        "source_stay_minutes": None
                        if p.stay is None
                        else {"minutes": p.stay[0], "source": [p.stay[1], p.stay[2]]},
                        "stay_note": p.stay_note,
                        "service_status": p.service_status,
                        "public_access": p.public_access,
                        "members": [[m.dataset_key, m.source_key] for m in p.members],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    with (clean / "source_records.jsonl").open("w", encoding="utf-8") as f:
        for p in places:
            for m in p.members:
                f.write(
                    json.dumps(
                        {
                            "dataset_key": m.dataset_key,
                            "source_key": m.source_key,
                            "name": m.name,
                            "address": m.address,
                            "city": m.city,
                            "lat": m.lat,
                            "lon": m.lon,
                            "coord_note": m.coord_note,
                            "source_updated_at": m.source_updated_at,
                            "service_status": m.service_status,
                            "public_access": m.public_access,
                            "display": m.display,
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                    + "\n"
                )

    def write_csv(path: Path, header: list[str], rows) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)

    write_csv(
        review / "exclusions.csv",
        ["dataset_key", "source_key", "name", "reason"],
        [[e.dataset_key, e.source_key, e.name, e.reason] for e in exclusions],
    )
    write_csv(
        review / "dedup_review.csv",
        [
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
        ],
        [
            [
                r.dataset_key,
                r.source_key,
                r.name,
                r.address,
                r.target_dataset_key,
                r.target_source_key,
                r.target_name,
                r.target_address,
                r.distance_m,
                r.rule,
                "",
            ]
            for r in reviews
        ],
    )
    write_csv(
        review / "facility_unattached.csv",
        ["dataset_key", "source_key", "facility", "venue_name", "category", "reason"],
        [[p.dataset_key, p.source_key, p.facility, p.venue_name, p.category, why] for p, why in unattached],
    )

    kinds = Counter(p.kind for p in places)
    ptypes = Counter(p.primary_type for p in places if p.kind == "attraction")
    fac = Counter(f_ for p in places for f_, (a, _, _) in p.facilities.items() if a.value == "yes")
    fam_lodging = sum(
        1
        for p in places
        if p.kind == "lodging"
        and any(
            p.facilities.get(f_) and p.facilities[f_][0].value == "yes"
            for f_ in ("crib", "baby_bathtub", "kids_play_area")
        )
    )
    multi = sum(1 for p in places if len(p.members) > 1)
    summary = {
        "today": today.isoformat(),
        "loaded_per_dataset": dict(per_ds),
        "places": dict(kinds),
        "attraction_primary_types": dict(ptypes),
        "places_merged_from_multiple_sources": multi,
        "facility_yes_counts": dict(fac),
        "lodging_with_family_facility_evidence": fam_lodging,
        "indoor": dict(
            Counter(
                f"{p.indoor.value}/{p.indoor.confirmation}" if p.indoor else "unknown"
                for p in places
                if p.kind == "attraction"
            )
        ),
        "source_stay_minutes_adopted": sum(1 for p in places if p.stay),
        "stay_not_adopted_conflict": sum(1 for p in places if p.stay_note),
        "age_ranges_with_evidence": 0,
        "exclusions": dict(Counter(e.dataset_key for e in exclusions)),
        "exclusion_reasons": dict(Counter(e.reason.split("（")[0] for e in exclusions)),
        "dedup_review_items": len(reviews),
        "facility_points_attached": sum(len(c.attached_points) for c in clusters),
        "facility_points_unattached": len(unattached),
    }
    (clean / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=Path("../data/raw"))
    ap.add_argument("--out", type=Path, default=Path("../data"))
    ap.add_argument("--today", type=date.fromisoformat, default=date.today())
    a = ap.parse_args()
    print(json.dumps(run(a.raw, a.out, a.today), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
