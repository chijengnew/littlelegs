"""基礎設施整合測試：限流 delta 准入、協調鎖、刪除恢復、匯入下架規則、UUIDv7 二進位順序。"""

from __future__ import annotations

import asyncio
import csv
import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.locks import lock_name, uid_lock
from app.db.models import Favorite, Place, RateCounter, SourceRecord
from app.ids import new_id
from app.ratelimit import Counter, QuotaExceeded, admit
from app.services import deletion

from .conftest import DB_URL, NOW
from .test_api_flows import auth, cond, v7

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


async def test_admit_delta_and_full_rollback(env):
    st = env["st"]
    await admit(st.factory, [Counter("t:elements", "day", 60, 49), Counter("t:req", "day", 5, 1)], NOW)
    with pytest.raises(QuotaExceeded):
        await admit(st.factory, [Counter("t:elements", "day", 60, 49), Counter("t:req", "day", 5, 1)], NOW)
    async with st.factory() as s:
        rows = dict(
            (
                await s.execute(
                    select(RateCounter.counter_key, RateCounter.count).where(RateCounter.counter_key.like("t:%"))
                )
            ).all()
        )
    assert rows == {"t:elements": 49, "t:req": 1}


async def test_admit_concurrent_never_exceeds(env):
    st = env["st"]

    async def one():
        try:
            await admit(st.factory, [Counter("t:conc", "minute", 10, 1)], NOW)
            return True
        except QuotaExceeded:
            return False

    results = await asyncio.gather(*(one() for _ in range(25)))
    assert sum(results) == 10


async def test_uid_lock_released_and_cancellation_safe(env):
    st = env["st"]
    eng = st.engine
    async with uid_lock(eng, "uid-a"):
        async with eng.connect() as other:
            assert await other.scalar(text("SELECT IS_FREE_LOCK(:n)"), {"n": lock_name("uid-a")}) == 0
    async with eng.connect() as c:
        assert await c.scalar(text("SELECT IS_FREE_LOCK(:n)"), {"n": lock_name("uid-a")}) == 1

    started = asyncio.Event()

    async def holder():
        async with uid_lock(eng, "uid-b"):
            started.set()
            await asyncio.sleep(30)

    t = asyncio.create_task(holder())
    await started.wait()
    t.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t
    async with eng.connect() as c:
        assert await c.scalar(text("SELECT IS_FREE_LOCK(:n)"), {"n": lock_name("uid-b")}) == 1


async def test_intent_accepted_local_failure_recovered_by_worker(env, monkeypatch):
    c, st, ids = env["client"], env["st"], env["ids"]
    fav = await c.post(
        "/v1/favorites",
        json={"conditions": cond(), "stops": [{"place_id": str(ids["museum"])}]},
        headers={**auth(), "Idempotency-Key": v7()},
    )
    fid = fav.json()["favorite"]["id"]
    real = deletion._delete_favorite_rows

    async def boom(*a, **k):
        raise RuntimeError("模擬 MySQL 失敗")

    monkeypatch.setattr(deletion, "_delete_favorite_rows", boom)
    op = v7()
    r = await c.delete(f"/v1/favorites/{fid}", headers={**auth(), "Idempotency-Key": op})
    assert r.status_code == 202 and r.json()["status"] == "accepted"
    assert len(await st.intents.list_pending()) == 1
    monkeypatch.setattr(deletion, "_delete_favorite_rows", real)
    for it in await st.intents.list_pending():
        await deletion.process_intent(st, it)
    assert await st.intents.list_pending() == []
    async with st.factory() as s:
        assert (await s.execute(select(Favorite.id))).first() is None
    again = await c.delete(f"/v1/favorites/{fid}", headers={**auth(), "Idempotency-Key": op})
    assert again.status_code == 200 and again.json()["status"] == "completed"


async def test_uuid7_binary_order_matches_string_order(env):
    st = env["st"]
    async with st.factory() as s:
        rows = (await s.execute(text("SELECT id FROM places ORDER BY id"))).scalars().all()
    import uuid

    as_uuid = [uuid.UUID(bytes=b) for b in rows]
    assert as_uuid == sorted(as_uuid, key=str)


def _write_data(tmp, members_a: list[str], members_b: list[str]):
    (tmp / "clean").mkdir(parents=True, exist_ok=True)
    with (tmp / "manifest_complete.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        cols = [
            "dataset_key",
            "title",
            "provider",
            "source_url",
            "license",
            "license_url",
            "license_status",
            "license_checked_at",
            "source_updated_at",
            "downloaded_at",
            "crs",
            "role",
            "import_policy",
            "notes",
        ]
        w.writerow(cols)
        for k in ("ds_a", "ds_b"):
            w.writerow(
                [k, k, "p", "https://x", "L", "", "verified", "", "", "2026-10-16", "WGS84", "primary", "import", ""]
            )
    places, srcs = [], []
    if "k1" in members_a or "k2" in members_b:
        mem = [["ds_a", "k1"]] * ("k1" in members_a) + [["ds_b", "k2"]] * ("k2" in members_b)
        places.append(
            {
                "kind": "attraction",
                "name": "P",
                "address": None,
                "city": "臺北市",
                "lat": 25.0,
                "lon": 121.5,
                "coord_source": mem[0],
                "types": {},
                "primary_type": "other",
                "indoor": None,
                "facilities": {},
                "source_stay_minutes": None,
                "members": mem,
            }
        )
    if "k3" in members_a:
        places.append(
            {
                "kind": "attraction",
                "name": "Q",
                "address": None,
                "city": "臺北市",
                "lat": 25.1,
                "lon": 121.5,
                "coord_source": ["ds_a", "k3"],
                "types": {},
                "primary_type": "other",
                "indoor": None,
                "facilities": {},
                "source_stay_minutes": None,
                "members": [["ds_a", "k3"]],
            }
        )
    if "k4" in members_a:
        places.append(
            {
                "kind": "attraction",
                "name": "R",
                "address": None,
                "city": "臺北市",
                "lat": 25.2,
                "lon": 121.5,
                "coord_source": ["ds_a", "k4"],
                "types": {},
                "primary_type": "other",
                "indoor": None,
                "facilities": {},
                "source_stay_minutes": None,
                "members": [["ds_a", "k4"]],
            }
        )
    for ds, keys in (("ds_a", members_a), ("ds_b", members_b)):
        for k in keys:
            srcs.append({"dataset_key": ds, "source_key": k, "name": k, "lat": 25.0, "lon": 121.5, "display": {}})
    (tmp / "clean" / "places.jsonl").write_text("\n".join(json.dumps(p) for p in places), encoding="utf-8")
    (tmp / "clean" / "source_records.jsonl").write_text("\n".join(json.dumps(s) for s in srcs), encoding="utf-8")


async def _state(names=("P", "Q")):
    eng = create_async_engine(DB_URL)
    f = async_sessionmaker(eng)
    async with f() as s:
        rows = {r.name: r for r in (await s.execute(select(Place).where(Place.name.in_(names)))).scalars()}
        srcs = {r.source_key: r.removed_at for r in (await s.execute(select(SourceRecord))).scalars()}
    await eng.dispose()
    return rows, srcs


async def test_import_removal_rules(seeded, tmp_path, monkeypatch):
    from etl import load_db

    _write_data(tmp_path, ["k1", "k3"], ["k2"])
    await load_db.run(tmp_path, "full", DB_URL)
    rows, _ = await _state()
    pid_p = rows["P"].id

    _write_data(tmp_path, [], ["k2"])
    await load_db.run(tmp_path, "incremental", DB_URL)
    rows, srcs = await _state()
    assert srcs["k1"] is None and rows["Q"].removed_at is None

    real = load_db._mark_removed

    async def boom(*a, **k):
        raise RuntimeError("模擬匯入失敗")

    monkeypatch.setattr(load_db, "_mark_removed", boom)
    with pytest.raises(RuntimeError):
        await load_db.run(tmp_path, "full", DB_URL)
    rows, srcs = await _state()
    assert srcs["k1"] is None and rows["Q"].removed_at is None
    monkeypatch.setattr(load_db, "_mark_removed", real)

    _write_data(tmp_path, [], ["k2"])
    await load_db.run(tmp_path, "full", DB_URL)
    rows, srcs = await _state()
    assert srcs["k1"] is None and rows["Q"].removed_at is None

    _write_data(tmp_path, ["k4"], ["k2"])
    await load_db.run(tmp_path, "full", DB_URL)
    rows, srcs = await _state()
    assert srcs["k1"] is not None and srcs["k3"] is not None and srcs["k2"] is None
    assert rows["P"].removed_at is None and rows["P"].id == pid_p
    assert rows["Q"].removed_at is not None
    _ = datetime.now(UTC), new_id


async def test_import_split_cluster_gets_distinct_ids(seeded, tmp_path):
    """既有地點的來源被拆到兩個叢集時，不得重用同一內部 ID（曾造成 place_types 主鍵衝突）。"""
    from etl import load_db

    def write(places):
        _write_data(tmp_path, ["k1"], ["k2"])
        (tmp_path / "clean" / "places.jsonl").write_text("\n".join(json.dumps(p) for p in places), encoding="utf-8")

    def place(name, members):
        return {
            "kind": "attraction",
            "name": name,
            "address": None,
            "city": "臺北市",
            "lat": 25.0,
            "lon": 121.5,
            "coord_source": members[0],
            "types": {
                "other": {
                    "value": True,
                    "confirmation": "confirmed",
                    "evidence": "t",
                    "source_type": "open_data",
                    "verified_at": None,
                    "source": members[0],
                }
            },
            "primary_type": "other",
            "indoor": None,
            "facilities": {},
            "source_stay_minutes": None,
            "members": members,
        }

    write([place("P", [["ds_a", "k1"], ["ds_b", "k2"]])])
    await load_db.run(tmp_path, "full", DB_URL)
    rows, _ = await _state(("P",))
    old = rows["P"].id
    write([place("P", [["ds_a", "k1"]]), place("P2", [["ds_b", "k2"]])])
    stats = await load_db.run(tmp_path, "full", DB_URL)
    rows, _ = await _state(("P", "P2"))
    assert {rows["P"].id, rows["P2"].id} == {old, rows["P2"].id} and rows["P"].id != rows["P2"].id
    assert stats["place_identity_conflicts"] == 1


async def test_import_merge_keeps_place_with_google_place_id(seeded, tmp_path):
    """兩個既有地點整併時，保留已配對 Place ID 的那一個（即使它的內部 ID 較新）。"""
    from sqlalchemy import update

    from etl import load_db

    def place(name, members):
        return {
            "kind": "attraction",
            "name": name,
            "address": None,
            "city": "臺北市",
            "lat": 25.0,
            "lon": 121.5,
            "coord_source": members[0],
            "types": {},
            "primary_type": None,
            "indoor": None,
            "facilities": {},
            "source_stay_minutes": None,
            "members": members,
        }

    def write(places):
        _write_data(tmp_path, ["k1"], ["k2"])
        (tmp_path / "clean" / "places.jsonl").write_text("\n".join(json.dumps(p) for p in places), encoding="utf-8")

    write([place("A", [["ds_a", "k1"]]), place("B", [["ds_b", "k2"]])])
    await load_db.run(tmp_path, "full", DB_URL)
    rows, _ = await _state(("A", "B"))
    newer = max(rows["A"].id, rows["B"].id, key=lambda u: u.bytes)
    eng = create_async_engine(DB_URL)
    async with eng.begin() as c:
        await c.execute(
            update(Place).where(Place.id == newer).values(google_place_id="ChIJmatched", place_id_status="accepted")
        )
    await eng.dispose()
    write([place("A", [["ds_a", "k1"], ["ds_b", "k2"]])])
    stats = await load_db.run(tmp_path, "full", DB_URL)
    eng = create_async_engine(DB_URL)
    async with async_sessionmaker(eng)() as sess:
        kept = await sess.get(Place, newer)
        older = await sess.get(Place, min(rows["A"].id, rows["B"].id, key=lambda u: u.bytes))
    await eng.dispose()
    assert kept is not None and kept.name == "A" and kept.removed_at is None and kept.google_place_id == "ChIJmatched"
    assert older is not None and older.removed_at is not None
    assert stats["places_soft_deleted"] == 1


async def test_place_id_export_import_by_source_keys(seeded, tmp_path, monkeypatch):
    """匯出 → 目標資料庫（以清空 Place ID 模擬）匯入：依來源紀錄鍵寫回、保留查核時間、已有人工結論者不覆寫。"""
    from argparse import Namespace

    from sqlalchemy import update

    from app.config import get_settings
    from scripts import place_ids

    checked = datetime(2026, 10, 22, 13, 40, tzinfo=UTC)
    eng = create_async_engine(DB_URL)
    async with eng.begin() as c:
        await c.execute(update(Place).where(Place.id == seeded["museum"]).values(place_id_checked_at=checked))
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    get_settings.cache_clear()
    try:
        out = tmp_path / "export.csv"
        await place_ids.cmd_export(Namespace(out=str(out)))
        with out.open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        assert {(r["google_place_id"], r["source_key"]) for r in rows} == {
            ("ChIJmuseum", "museum"),
            ("ChIJpark", "park"),
            ("ChIJfactory", "factory"),
        }
        async with eng.begin() as c:
            await c.execute(
                update(Place).values(google_place_id=None, place_id_status="none", place_id_checked_at=None)
            )
            await c.execute(update(Place).where(Place.id == seeded["park"]).values(place_id_status="no_match"))

        await place_ids.cmd_import(Namespace(csv=str(out), dry_run=True))
        async with async_sessionmaker(eng)() as s:
            assert (await s.execute(select(Place).where(Place.google_place_id.is_not(None)))).first() is None

        await place_ids.cmd_import(Namespace(csv=str(out), dry_run=False))
        await place_ids.cmd_import(Namespace(csv=str(out), dry_run=False))
        async with async_sessionmaker(eng)() as s:
            got = {p.id: p for p in (await s.execute(select(Place))).scalars()}
    finally:
        get_settings.cache_clear()
        await eng.dispose()
    museum, park, factory = got[seeded["museum"]], got[seeded["park"]], got[seeded["factory"]]
    assert (museum.google_place_id, museum.place_id_status) == ("ChIJmuseum", "accepted")
    assert museum.place_id_checked_at is not None and museum.place_id_checked_at.replace(tzinfo=UTC) == checked
    assert (factory.google_place_id, factory.place_id_status) == ("ChIJfactory", "accepted")
    assert (park.google_place_id, park.place_id_status) == (None, "no_match")
