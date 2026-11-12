"""探險護照端對端流程：蓋章、升級、不可降級、冪等、刪除、任務計數與會員隔離。真實 MySQL＋FastAPI。"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import update

from app.db.models import CheckIn, CheckInOperation, Place, User

from .conftest import NOW
from .test_api_flows import auth, count, v7

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

PARK = (25.0300, 121.5350)
MUSEUM = (25.0400, 121.5600)


def at(lat: float, lng: float, accuracy_m: float = 20) -> dict:
    return {"lat": lat, "lng": lng, "accuracy_m": accuracy_m}


def stamp(place_id, method: str = "location", where: dict | None = None) -> dict:
    body: dict = {"place_id": str(place_id), "verification_method": method}
    if method == "location":
        body["location"] = where if where is not None else at(*PARK)
    return body


async def post(c, body, uid: str = "u1", key: str | None = None):
    return await c.post("/v1/check-ins", json=body, headers={**auth(uid), "Idempotency-Key": key or v7()})


async def test_members_only(env):
    c, ids = env["client"], env["ids"]
    guest = await c.post("/v1/check-ins", json=stamp(ids["park"]), headers={"Idempotency-Key": v7()})
    assert guest.status_code == 401 and guest.json()["code"] == "AUTH_REQUIRED"
    unverified = await post(c, stamp(ids["park"]), uid="unverified1")
    assert unverified.status_code == 403 and unverified.json()["code"] == "EMAIL_NOT_VERIFIED"
    assert (await c.get("/v1/check-ins")).status_code == 401
    assert (await c.get("/v1/missions")).status_code == 401
    place = await c.get(f"/v1/places/{ids['park']}", headers=auth())
    assert "check_in" not in place.text and "verification_method" not in place.text


async def test_manual_then_location_upgrade_keeps_first_record_time(env):
    c, st, ids, clock = env["client"], env["st"], env["ids"], env["clock"]
    m = await post(c, stamp(ids["park"], "manual"))
    assert m.status_code == 201 and m.json()["outcome"] == "created"
    first = m.json()["check_in"]
    assert first["verification_method"] == "manual" and first["verified_at"] is None
    assert first["place"] == {
        "place_id": str(ids["park"]),
        "name": "森林親子公園",
        "primary_type": "park_playground",
        "city": "臺北市",
        "removed": False,
    }
    again = await post(c, stamp(ids["park"], "manual"))
    assert again.status_code == 200 and again.json()["outcome"] == "existing"
    clock.now = NOW + timedelta(hours=2)
    try:
        up = await post(c, stamp(ids["park"]))
        assert up.status_code == 200 and up.json()["outcome"] == "upgraded"
        u = up.json()["check_in"]
        assert u["id"] == first["id"] and u["verification_method"] == "location"
        assert u["visited_at"] == first["visited_at"] and u["verified_at"] > u["visited_at"]
        down = await post(c, stamp(ids["park"], "manual"))
        assert down.status_code == 200 and down.json()["outcome"] == "existing"
        assert down.json()["check_in"]["verification_method"] == "location"
        assert down.json()["check_in"]["verified_at"] == u["verified_at"]
        relocate = await post(c, stamp(ids["park"]))
        assert relocate.json()["outcome"] == "existing"
        assert relocate.json()["check_in"]["verified_at"] == u["verified_at"]
    finally:
        clock.now = NOW
    assert await count(st, CheckIn) == 1


async def test_location_failures_create_nothing_and_are_not_replayed(env):
    c, st, ids = env["client"], env["st"], env["ids"]
    far = await post(c, stamp(ids["park"], where=at(PARK[0] + 0.002, PARK[1])))
    assert far.status_code == 422 and far.json()["code"] == "LOCATION_TOO_FAR"
    assert far.headers["content-type"].startswith("application/problem+json")
    assert "lat" not in far.text and str(PARK[0]) not in far.text
    vague = await post(c, stamp(ids["park"], where=at(*PARK, accuracy_m=150)))
    assert vague.status_code == 422 and vague.json()["code"] == "LOCATION_INACCURATE"
    assert await count(st, CheckIn) == 0 and await count(st, CheckInOperation) == 0
    key = v7()
    failed = await post(c, stamp(ids["park"], where=at(PARK[0] + 0.002, PARK[1])), key=key)
    assert failed.json()["code"] == "LOCATION_TOO_FAR"
    ok = await post(c, stamp(ids["park"]), key=key)
    assert ok.status_code == 201 and ok.json()["outcome"] == "created"
    replay = await post(c, stamp(ids["park"]), key=key)
    assert replay.status_code == 201 and replay.json()["outcome"] == "created"
    assert replay.json()["check_in"]["id"] == ok.json()["check_in"]["id"]
    conflict = await post(c, stamp(ids["park"], "manual"), key=key)
    assert conflict.status_code == 409 and conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"
    assert await count(st, CheckIn) == 1


async def test_key_time_and_format_rules(env):
    c, ids = env["client"], env["ids"]
    ahead = await post(c, stamp(ids["park"]), key=v7(NOW + timedelta(hours=25)))
    assert ahead.status_code == 409 and ahead.json()["code"] == "KEY_TIME_INVALID"
    old = await post(c, stamp(ids["park"]), key=v7(NOW - timedelta(days=7)))
    assert old.status_code == 409 and old.json()["code"] == "OPERATION_EXPIRED"
    bad = await post(c, stamp(ids["park"]), key="not-a-uuid")
    assert bad.status_code == 422
    missing = await c.post("/v1/check-ins", json=stamp(ids["park"]), headers=auth())
    assert missing.status_code == 422


async def test_only_active_attractions_with_coordinates_can_be_stamped(env):
    c, st, ids = env["client"], env["st"], env["ids"]
    hotel = await post(c, stamp(ids["hotel"], "manual"))
    assert hotel.status_code == 422 and hotel.json()["code"] == "PLACE_NOT_STAMPABLE"
    unknown = await post(c, stamp("0190a000-0000-7000-8000-00000000abcd", "manual"))
    assert unknown.status_code == 404 and unknown.json()["code"] == "PLACE_NOT_FOUND"
    async with st.factory() as s, s.begin():
        await s.execute(update(Place).where(Place.id == ids["factory"]).values(coord_source_record_id=None))
    nocoord = await post(c, stamp(ids["factory"], "manual"))
    assert nocoord.status_code == 422 and nocoord.json()["code"] == "PLACE_NO_COORDINATES"
    kept = await post(c, stamp(ids["museum"], where=at(*MUSEUM)))
    assert kept.status_code == 201
    async with st.factory() as s, s.begin():
        await s.execute(update(Place).where(Place.id == ids["museum"]).values(removed_at=NOW))
    removed = await post(c, stamp(ids["park"], "manual"))
    assert removed.status_code == 201
    blocked = await post(c, stamp(ids["museum"], "manual"))
    assert blocked.status_code == 409 and blocked.json()["code"] == "PLACE_REMOVED"
    listed = (await c.get(f"/v1/check-ins?place_id={ids['museum']}", headers=auth())).json()["items"]
    assert len(listed) == 1 and listed[0]["place"]["removed"] is True


async def test_list_filter_counts_pagination_and_isolation(env):
    c, ids = env["client"], env["ids"]
    await post(c, stamp(ids["park"]))
    await post(c, stamp(ids["museum"], "manual"))
    await post(c, stamp(ids["factory"], "manual"))
    page = (await c.get("/v1/check-ins?limit=2", headers=auth())).json()
    assert len(page["items"]) == 2 and page["next_cursor"]
    assert page["counts"] == {"total": 3, "location": 1, "manual": 2}
    rest = (await c.get(f"/v1/check-ins?limit=2&cursor={page['next_cursor']}", headers=auth())).json()
    assert len(rest["items"]) == 1 and rest["next_cursor"] is None
    seen = [x["place"]["place_id"] for x in page["items"] + rest["items"]]
    assert sorted(seen) == sorted(str(ids[k]) for k in ("park", "museum", "factory"))
    one = (await c.get(f"/v1/check-ins?place_id={ids['park']}", headers=auth())).json()
    assert [x["verification_method"] for x in one["items"]] == ["location"]
    assert (await c.get("/v1/check-ins?place_id=bad", headers=auth())).status_code == 422
    other = (await c.get("/v1/check-ins", headers=auth("u2"))).json()
    assert other["items"] == [] and other["counts"]["total"] == 0
    cid = one["items"][0]["id"]
    steal = await c.delete(f"/v1/check-ins/{cid}", headers={**auth("u2"), "Idempotency-Key": v7()})
    assert steal.status_code == 404 and steal.json()["code"] == "CHECK_IN_NOT_FOUND"


async def test_delete_blocks_replay_and_updates_missions(env):
    c, st, ids = env["client"], env["st"], env["ids"]
    key = v7()
    r = await post(c, stamp(ids["park"]), key=key)
    cid = r.json()["check_in"]["id"]
    before = {m["code"]: m for m in (await c.get("/v1/missions", headers=auth())).json()["items"]}
    assert before["first_stamp"]["unlocked"] is True and before["park_explorer"]["progress"] == 1
    op = v7()
    d = await c.delete(f"/v1/check-ins/{cid}", headers={**auth(), "Idempotency-Key": op})
    assert d.status_code == 200 and d.json()["status"] == "completed"
    again = await c.delete(f"/v1/check-ins/{cid}", headers={**auth(), "Idempotency-Key": op})
    assert again.status_code == 200 and again.json()["status"] == "completed"
    assert await count(st, CheckIn) == 0
    replay = await post(c, stamp(ids["park"]), key=key)
    assert replay.status_code == 409 and replay.json()["code"] == "OPERATION_CANCELLED"
    assert await count(st, CheckIn) == 0
    after = {m["code"]: m for m in (await c.get("/v1/missions", headers=auth())).json()["items"]}
    assert after["first_stamp"] == {**before["first_stamp"], "progress": 0, "unlocked": False}
    fresh = await post(c, stamp(ids["park"]))
    assert fresh.status_code == 201 and fresh.json()["check_in"]["id"] != cid


async def test_missions_count_only_location_and_active_places(env):
    c, st, ids = env["client"], env["st"], env["ids"]
    await post(c, stamp(ids["park"]))
    await post(c, stamp(ids["museum"], "manual"))
    await post(c, stamp(ids["factory"], "manual"))
    m = (await c.get("/v1/missions", headers=auth())).json()
    by = {x["code"]: x for x in m["items"]}
    assert m["counted_places"] == 1
    assert by["first_stamp"] == {
        "code": "first_stamp",
        "kind": "distinct_places",
        "threshold": 1,
        "types": [],
        "progress": 1,
        "unlocked": True,
    }
    assert by["park_explorer"]["types"] == ["park_playground"] and by["park_explorer"]["progress"] == 1
    assert by["culture_scholar"]["progress"] == 0
    await post(c, stamp(ids["museum"], where=at(*MUSEUM)))
    by = {x["code"]: x for x in (await c.get("/v1/missions", headers=auth())).json()["items"]}
    assert by["culture_scholar"]["progress"] == 1 and by["little_explorer"]["progress"] == 2
    async with st.factory() as s, s.begin():
        await s.execute(update(Place).where(Place.id == ids["museum"]).values(removed_at=NOW))
    by = {x["code"]: x for x in (await c.get("/v1/missions", headers=auth())).json()["items"]}
    assert by["culture_scholar"]["progress"] == 0 and by["little_explorer"]["progress"] == 1
    other = (await c.get("/v1/missions", headers=auth("u2"))).json()
    assert other["counted_places"] == 0


async def test_stamp_rate_limit_per_uid(env):
    c, ids = env["client"], env["ids"]
    codes = [(await post(c, stamp(ids["park"], "manual"), uid="busy")).status_code for _ in range(11)]
    assert codes[0] == 201 and codes[1:10] == [200] * 9 and codes[10] == 429
    other = await post(c, stamp(ids["park"], "manual"), uid="calm")
    assert other.status_code == 201


async def test_account_deletion_removes_check_ins(env):
    c, st, ids, clock = env["client"], env["st"], env["ids"], env["clock"]
    await post(c, stamp(ids["park"]), uid="leaver")
    assert await count(st, CheckIn) == 1
    ok = await c.delete("/v1/me", headers={**auth("leaver", int(clock().timestamp()) - 60), "Idempotency-Key": v7()})
    assert ok.status_code == 200
    assert await count(st, User) == 0 and await count(st, CheckIn) == 0 and await count(st, CheckInOperation) == 0
