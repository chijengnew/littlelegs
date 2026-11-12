"""端對端 API 流程（一致性驗收）。真實 MySQL＋FastAPI；Firebase 與 Google 以 fake 取代。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.api.problems import Problem
from app.db.models import Favorite, History, PrivateEndpoint, RateCounter, User
from app.services.registration import purge_expired

from .conftest import NOW

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


def v7(dt: datetime = NOW, salt: int = 0) -> str:
    ms = int(dt.timestamp() * 1000)
    return str(uuid.UUID(int=(ms << 80) | (0x7 << 76) | (0b10 << 62) | (uuid.uuid4().int & ((1 << 62) - 1)) ^ salt))


def cond(**kw) -> dict:
    base = {
        "date": "2026-10-22",
        "depart_time": "09:00",
        "return_time": "18:00",
        "start": {"type": "device_coordinate", "lat": 25.0330, "lng": 121.5654},
        "children_ages": [4, 7],
        "lunch": {"start": "11:30", "end": "13:30"},
    }
    base.update(kw)
    return base


def auth(uid: str = "u1", auth_time: int | None = None) -> dict:
    tok = f"tok:{uid}" + (f":{auth_time}" if auth_time is not None else "")
    return {"Authorization": f"Bearer {tok}"}


async def count(st, model, **where) -> int:
    async with st.factory() as s:
        q = select(func.count()).select_from(model)
        for k, v in where.items():
            q = q.where(getattr(model, k) == v)
        return (await s.execute(q)).scalar_one()


async def test_guest_candidates_no_history_no_coords(env):
    c, st = env["client"], env["st"]
    r = await c.post("/v1/trips/candidates", json={"query_id": v7(), "conditions": cond()})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["history"] is None and body["map"]["mode"] == "locked_illustration"
    names = [x["name"] for x in body["candidates"]]
    assert set(names) == {"兒童探索博物館", "森林親子公園", "糖果觀光工廠"}
    assert all("location" not in x or x["location"] is None for x in body["candidates"])
    assert all(x["age"] == "estimated" and x["age_range"]["confirmation"] == "estimated" for x in body["candidates"])
    assert not any(w["code"] == "age_unknown" for x in body["candidates"] for w in x["warnings"])
    assert body["lodging"]["items"][0]["family_facilities"] == ["crib"]
    assert await count(st, History) == 0
    assert "matrix" not in " ".join(st.google.calls)
    assert "weather" in st.google.calls and body["weather"] is None
    assert "place_hours" not in st.google.calls
    for x in body["candidates"]:
        assert "hours" not in x
        assert any(w["code"] == "hours_checked_when_planning" for w in x["warnings"])
        assert not any(w["code"] == "hours_unknown" for w in x["warnings"])


async def test_member_search_creates_single_history_and_conflicts(env):
    c, st = env["client"], env["st"]
    qid = v7()
    r1 = await c.post("/v1/trips/candidates", json={"query_id": qid, "conditions": cond()}, headers=auth())
    assert r1.status_code == 200, r1.text
    assert r1.json()["history"]["status"] == "succeeded"
    assert r1.json()["map"]["mode"] == "google_map"
    r2 = await c.post("/v1/trips/candidates", json={"query_id": qid, "conditions": cond()}, headers=auth())
    assert r2.status_code == 200
    assert await count(st, History) == 1
    r3 = await c.post(
        "/v1/trips/candidates", json={"query_id": qid, "conditions": cond(children_ages=[2])}, headers=auth()
    )
    assert r3.status_code == 409 and r3.json()["code"] == "QUERY_CONDITIONS_CONFLICT"
    assert r3.headers["content-type"].startswith("application/problem+json")
    r4 = await c.post(
        "/v1/trips/candidates", json={"query_id": v7(), "conditions": cond(children_ages=[2])}, headers=auth()
    )
    assert r4.status_code == 200 and await count(st, History) == 2


async def test_rain_indoor_only_filters_to_indoor(env):
    c, st = env["client"], env["st"]
    st.google.forecast = [
        {
            "daytimeForecast": {
                "interval": {"startTime": "2026-10-21T23:00:00Z", "endTime": "2026-10-22T11:00:00Z"},
                "precipitation": {"probability": {"percent": 80, "type": "RAIN"}},
            },
            "nighttimeForecast": {
                "interval": {"startTime": "2026-10-22T11:00:00Z", "endTime": "2026-10-22T23:00:00Z"},
                "precipitation": {"probability": {"percent": 10, "type": "RAIN"}},
            },
        }
    ]
    r = await c.post("/v1/trips/candidates", json={"query_id": v7(), "conditions": cond(rain_indoor_only=True)})
    body = r.json()
    assert body["weather"]["status"] == "triggered" and body["weather"]["rain_filter"] is True
    assert body["weather"]["areas"][0]["roles"][0] == "start"
    assert {x["name"] for x in body["candidates"]} == {"兒童探索博物館", "糖果觀光工廠"}
    assert all(any(w["code"] == "indoor_inferred" for w in x["warnings"]) for x in body["candidates"])
    assert all(x["weather_area"] is not None for x in body["candidates"])


async def test_weather_shown_without_rain_filter(env):
    c, st = env["client"], env["st"]
    st.google.forecast = [
        {
            "daytimeForecast": {
                "interval": {"startTime": "2026-10-21T23:00:00Z", "endTime": "2026-10-22T11:00:00Z"},
                "precipitation": {"probability": {"percent": 80, "type": "RAIN"}},
            },
        }
    ]
    r = await c.post("/v1/trips/candidates", json={"query_id": v7(), "conditions": cond()})
    body = r.json()
    assert body["operation"] == "ok"
    assert body["weather"]["status"] == "not_requested" and body["weather"]["rain_filter"] is False
    assert body["weather"]["areas"][0]["max_precipitation_percent"] == 80
    assert {x["name"] for x in body["candidates"]} == {"兒童探索博物館", "森林親子公園", "糖果觀光工廠"}
    assert all(x["weather_area"] is not None for x in body["candidates"])


async def test_departure_passed_and_invalid_input(env):
    c = env["client"]
    r = await c.post(
        "/v1/trips/candidates",
        json={
            "query_id": v7(),
            "conditions": cond(date="2026-10-20", depart_time="08:45", return_time="12:00", lunch=None),
        },
    )
    assert r.status_code == 409 and r.json()["code"] == "DEPARTURE_PASSED"
    assert r.headers["content-type"].startswith("application/problem+json")
    Problem.model_validate(r.json())
    r = await c.post("/v1/trips/candidates", json={"query_id": v7(), "conditions": cond(children_ages=[])})
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_FAILED"
    Problem.model_validate(r.json())
    assert "4" not in str(r.json().get("errors"))
    r = await c.post("/v1/trips/candidates", json={"query_id": v7().upper(), "conditions": cond()})
    assert r.status_code == 422


async def test_sort_check_revision_flow(env):
    c, st, ids = env["client"], env["st"], env["ids"]
    qid = v7()
    r = await c.post("/v1/trips/candidates", json={"query_id": qid, "conditions": cond()}, headers=auth())
    rev = r.json()["history"]["revision"]
    stops = [{"place_id": str(ids["museum"])}, {"place_id": str(ids["park"])}]
    s1 = await c.post(
        "/v1/trips/sort",
        json={"query_id": qid, "conditions": cond(), "stops": stops, "expected_revision": rev},
        headers=auth(),
    )
    assert s1.status_code == 200, s1.text
    b = s1.json()
    assert "weather" in st.google.calls and b["weather"] is None
    assert b["feasibility"] == "feasible"
    assert any(w["code"] == "special_hours_unverified" for w in b["warnings"])
    assert b["history"]["revision"] == rev + 1
    assert all(x["google_place_id"].startswith("ChIJ") for x in b["stops"])
    assert all(x["primary_type"] for x in b["stops"])
    assert b["start"]["coordinate"] == {"lat": 25.033, "lng": 121.5654}
    assert b["map"]["connect_line"] and b["map"]["line_note"] == "順序示意，非道路導航"
    types = [i["type"] for i in b["timeline"]]
    assert types[0] == "move" and types.count("move") == len(stops) + 1 and "meal" in types
    assert not any(i["type"] == "rest" and i["reason"] == "arrival_buffer" for i in b["timeline"])
    stale = await c.post(
        "/v1/trips/check",
        json={"query_id": qid, "conditions": cond(), "stops": stops[::-1], "expected_revision": rev},
        headers=auth(),
    )
    assert stale.status_code == 409 and stale.json()["code"] == "REVISION_CONFLICT"
    before = st.google.calls.count("matrix:3")
    chk = await c.post(
        "/v1/trips/check",
        json={"query_id": qid, "conditions": cond(), "stops": stops[::-1], "expected_revision": rev + 1},
        headers=auth(),
    )
    assert chk.json()["order"] == [str(ids["park"]), str(ids["museum"])]
    assert st.google.calls.count("matrix:3") == before + 1
    async with st.factory() as s:
        cnt = (
            await s.execute(select(RateCounter.count).where(RateCounter.counter_key == "g:matrix_elements"))
        ).scalar_one()
    assert cnt == 9 * 2


async def test_matrix_failure_is_unverified_not_infeasible(env):
    c, st, ids = env["client"], env["st"], env["ids"]
    st.google.fail_matrix = True
    r = await c.post(
        "/v1/trips/check", json={"query_id": v7(), "conditions": cond(), "stops": [{"place_id": str(ids["museum"])}]}
    )
    b = r.json()
    assert r.status_code == 200 and b["feasibility"] == "unverified" and b["timeline"] == []
    assert b["operation"] == "partial" and any(w["code"] == "travel_unavailable" for w in b["warnings"])


async def test_monthly_cap_degrades_hours_without_failing(env):
    import dataclasses

    c, st, ids = env["client"], env["st"], env["ids"]
    st.limiter.lim = dataclasses.replace(st.limiter.lim, monthly_place_details_enterprise=1)
    r = await c.post(
        "/v1/trips/check",
        json={
            "query_id": v7(),
            "conditions": cond(),
            "stops": [{"place_id": str(ids["museum"])}, {"place_id": str(ids["park"])}],
        },
    )
    assert r.status_code == 200, r.text
    b = r.json()
    hours = [s["hours"] for s in b["stops"]]
    assert sorted(h["status"] for h in hours) == ["provisional", "unknown"]
    assert any("本月營業時間查詢額度已用完" in n for h in hours for n in h["notes"])
    assert b["feasibility"] == "unverified"
    async with st.factory() as s:
        row = (
            await s.execute(select(RateCounter).where(RateCounter.counter_key == "gm:place_details_enterprise"))
        ).scalar_one()
    assert row.count == 1
    assert row.window_start == datetime(2026, 10, 1, 7, 0, tzinfo=UTC)


async def test_monthly_cap_on_endpoint_resolve_is_problem_json(env):
    import dataclasses

    c, st = env["client"], env["st"]
    st.limiter.lim = dataclasses.replace(st.limiter.lim, monthly_place_details_essentials=0)
    r = await c.post("/v1/endpoints/resolve", json={"google_place_id": "ChIJhome", "session_token": str(uuid.uuid4())})
    assert r.status_code == 429 and r.json()["code"] == "MONTHLY_QUOTA_EXHAUSTED"
    assert r.headers["content-type"].startswith("application/problem+json")


async def test_place_detail_hides_coords_for_guests_and_lists_evidence(env):
    c, ids = env["client"], env["ids"]
    path = f"/v1/places/{ids['museum']}"
    g = await c.get(path)
    assert g.status_code == 200, g.text
    body = g.json()
    assert body["place"]["location"] is None
    assert body["place"]["age_range"] == {"min_age": 7, "max_age": 18, "confirmation": "estimated"}
    ev = body["evidence"]
    assert ev["indoor"]["value"] == "indoor" and ev["indoor"]["confirmation"] == "inferred"
    assert ev["types"][0]["evidence_record_id"] and ev["age_ranges"] == [] and ev["age_exclusions"] == []
    m = await c.get(path, headers=auth())
    assert m.status_code == 200, m.text
    assert m.json()["place"]["location"]["source"] == "open_data"
    assert (await c.get(f"/v1/places/{v7()}")).status_code == 404


async def test_infeasible_is_200_with_violations(env):
    c, ids = env["client"], env["ids"]
    r = await c.post(
        "/v1/trips/sort",
        json={
            "query_id": v7(),
            "conditions": cond(return_time="11:00", lunch=None),
            "stops": [{"place_id": str(ids["museum"]), "stay_minutes": 120}],
        },
    )
    assert r.status_code == 200 and r.json()["feasibility"] == "infeasible"
    assert "RETURN_TIME_EXCEEDED" in r.json()["violation_codes"]


async def test_guest_import_once_and_conflict(env):
    c, st, ids = env["client"], env["st"], env["ids"]
    qid = v7()
    await c.post("/v1/trips/candidates", json={"query_id": qid, "conditions": cond()})
    body = {"query_id": qid, "conditions": cond(), "stops": [{"place_id": str(ids["museum"])}], "ordered": False}
    r1 = await c.post("/v1/histories/guest-import", json=body, headers=auth())
    assert r1.status_code == 201 and r1.json()["status"] == "guest_imported"
    r2 = await c.post("/v1/histories/guest-import", json=body, headers=auth())
    assert r2.status_code == 200 and r2.json()["id"] == r1.json()["id"]
    r3 = await c.post(
        "/v1/histories/guest-import", json={**body, "conditions": cond(children_ages=[1])}, headers=auth()
    )
    assert r3.status_code == 409
    assert await count(st, History) == 1


async def test_unverified_email_is_guest_for_queries_and_blocked_for_member_apis(env):
    c, st, ids = env["client"], env["st"], env["ids"]
    who = auth("unverified-u9")
    me = await c.get("/v1/me", headers=who)
    assert me.status_code == 403 and me.json()["code"] == "EMAIL_NOT_VERIFIED"
    assert me.headers["content-type"].startswith("application/problem+json")
    qid = v7()
    r = await c.post("/v1/trips/candidates", json={"query_id": qid, "conditions": cond()}, headers=who)
    assert r.status_code == 200, r.text
    assert r.json()["history"] is None and r.json()["map"]["mode"] == "locked_illustration"
    for method, path, body in (
        ("GET", "/v1/histories", None),
        ("GET", "/v1/favorites", None),
        (
            "POST",
            "/v1/histories/guest-import",
            {"query_id": qid, "conditions": cond(), "stops": [{"place_id": str(ids["museum"])}], "ordered": False},
        ),
    ):
        blocked = await c.request(method, path, json=body, headers=who)
        assert blocked.status_code == 403 and blocked.json()["code"] == "EMAIL_NOT_VERIFIED", (path, blocked.text)
    assert await count(st, User, firebase_uid="unverified-u9") == 0 and await count(st, History) == 0


async def test_favorite_idempotency_and_cancellation(env):
    c, st, ids = env["client"], env["st"], env["ids"]
    body = {"conditions": cond(), "stops": [{"place_id": str(ids["museum"])}], "saved_as": "unverified"}
    k1 = v7()
    r1 = await c.post("/v1/favorites", json=body, headers={**auth(), "Idempotency-Key": k1})
    assert r1.status_code == 201 and r1.json()["notice"].endswith("未於儲存時重新驗證")
    fid = r1.json()["favorite"]["id"]
    r2 = await c.post("/v1/favorites", json=body, headers={**auth(), "Idempotency-Key": k1})
    assert r2.status_code == 200 and r2.json()["favorite"]["id"] == fid
    r3 = await c.post("/v1/favorites", json={**body, "saved_as": "plan"}, headers={**auth(), "Idempotency-Key": k1})
    assert r3.status_code == 409 and r3.json()["code"] == "IDEMPOTENCY_CONFLICT"
    r4 = await c.post("/v1/favorites", json=body, headers={**auth(), "Idempotency-Key": v7()})
    assert r4.status_code == 200 and r4.json()["favorite"]["id"] == fid
    assert await count(st, Favorite) == 1
    d = await c.delete(f"/v1/favorites/{fid}", headers={**auth(), "Idempotency-Key": v7()})
    assert d.status_code == 200 and d.json()["status"] == "completed"
    r5 = await c.post("/v1/favorites", json=body, headers={**auth(), "Idempotency-Key": k1})
    assert r5.status_code == 409 and r5.json()["code"] == "OPERATION_CANCELLED"
    r6 = await c.post("/v1/favorites", json=body, headers={**auth(), "Idempotency-Key": v7()})
    assert r6.status_code == 201 and r6.json()["favorite"]["id"] != fid


async def test_favorite_key_time_rules(env):
    c, ids = env["client"], env["ids"]
    body = {"conditions": cond(), "stops": [{"place_id": str(ids["museum"])}]}
    ahead = await c.post(
        "/v1/favorites", json=body, headers={**auth(), "Idempotency-Key": v7(NOW + timedelta(hours=25))}
    )
    assert ahead.status_code == 409 and ahead.json()["code"] == "KEY_TIME_INVALID"
    old = await c.post("/v1/favorites", json=body, headers={**auth(), "Idempotency-Key": v7(NOW - timedelta(days=7))})
    assert old.status_code == 409 and old.json()["code"] == "OPERATION_EXPIRED"
    bad = await c.post("/v1/favorites", json=body, headers={**auth(), "Idempotency-Key": "not-a-uuid"})
    assert bad.status_code == 422


async def test_private_endpoint_reuse_and_cross_user_rejection(env):
    c, st, ids = env["client"], env["st"], env["ids"]
    home = {"type": "google_place", "google_place_id": "ChIJhome", "label": "家"}
    body = {"conditions": cond(start=home), "stops": [{"place_id": str(ids["park"])}]}
    r1 = await c.post("/v1/favorites", json=body, headers={**auth(), "Idempotency-Key": v7()})
    r2 = await c.post(
        "/v1/favorites",
        json={**body, "conditions": cond(start={**home, "label": "老家"})},
        headers={**auth(), "Idempotency-Key": v7()},
    )
    assert r1.json()["favorite"]["id"] == r2.json()["favorite"]["id"]
    assert await count(st, PrivateEndpoint) == 1
    eid = r1.json()["favorite"]["conditions"]["start"]["endpoint_id"]
    stolen = {"conditions": cond(start={**home, "endpoint_id": eid}), "stops": [{"place_id": str(ids["park"])}]}
    r3 = await c.post("/v1/favorites", json=stolen, headers={**auth("u2"), "Idempotency-Key": v7()})
    assert r3.status_code == 403 and r3.json()["code"] == "ENDPOINT_FORBIDDEN"
    await c.delete(f"/v1/favorites/{r1.json()['favorite']['id']}", headers={**auth(), "Idempotency-Key": v7()})
    assert await count(st, PrivateEndpoint) == 0


async def test_delete_history_keeps_favorite_and_blocks_replay(env):
    c, st, ids = env["client"], env["st"], env["ids"]
    qid = v7()
    r = await c.post("/v1/trips/candidates", json={"query_id": qid, "conditions": cond()}, headers=auth())
    hid = r.json()["history"]["id"]
    fav = await c.post(
        "/v1/favorites",
        json={"conditions": cond(), "stops": [{"place_id": str(ids["museum"])}], "source_history_id": hid},
        headers={**auth(), "Idempotency-Key": v7()},
    )
    assert fav.status_code == 201
    d = await c.delete(f"/v1/histories/{hid}", headers={**auth(), "Idempotency-Key": v7()})
    assert d.status_code == 200
    assert await count(st, History) == 0 and await count(st, Favorite) == 1
    got = await c.get(f"/v1/favorites/{fav.json()['favorite']['id']}", headers=auth())
    assert got.json()["source_history_id"] is None
    g = got.json()
    assert g["stops"][0]["location"]["source"] == "open_data"
    assert g["start_location"] == {"lat": 25.033, "lng": 121.5654, "source": "device", "persist": None}
    assert g["end_location"] == g["start_location"]
    assert g["stops"][0]["google_place_id"].startswith("ChIJ")
    assert g["stops"][0]["primary_type"]
    listed = (await c.get("/v1/favorites", headers=auth())).json()["items"][0]
    assert listed["stop_previews"] == [{"name": g["stops"][0]["name"], "primary_type": g["stops"][0]["primary_type"]}]
    assert listed.get("stops") is None
    assert g.get("stop_previews") is None
    assert g["start_endpoint"]["coordinate"] == {"lat": 25.033, "lng": 121.5654}
    assert g["end_endpoint"] == g["start_endpoint"]
    replay = await c.post("/v1/trips/candidates", json={"query_id": qid, "conditions": cond()}, headers=auth())
    assert replay.status_code == 409 and replay.json()["code"] == "HISTORY_DELETED"


async def test_cross_user_access_and_pagination(env):
    c = env["client"]
    for _ in range(3):
        await c.post("/v1/trips/candidates", json={"query_id": v7(), "conditions": cond()}, headers=auth())
    lst = await c.get("/v1/histories?limit=2", headers=auth())
    assert len(lst.json()["items"]) == 2 and lst.json()["next_cursor"]
    nxt = await c.get(f"/v1/histories?limit=2&cursor={lst.json()['next_cursor']}", headers=auth())
    assert len(nxt.json()["items"]) == 1
    hid = lst.json()["items"][0]["id"]
    assert lst.json()["items"][0]["start_place_name"] is None
    assert lst.json()["items"][0]["stop_previews"] == []
    assert (await c.get(f"/v1/histories/{hid}", headers=auth("intruder"))).status_code == 404
    assert (await c.get("/v1/histories?limit=51", headers=auth())).status_code == 422
    assert (await c.get("/v1/histories?limit=0", headers=auth())).status_code == 422


async def test_saved_items_show_place_names_for_place_ref(env):
    c = env["client"]
    museum = str(env["ids"]["museum"])
    body = {"query_id": v7(), "conditions": cond(start={"type": "place_ref", "place_id": museum})}
    assert (await c.post("/v1/trips/candidates", json=body, headers=auth("names"))).status_code == 200
    item = (await c.get("/v1/histories", headers=auth("names"))).json()["items"][0]
    assert item["start_place_name"] == item["end_place_name"] == "兒童探索博物館"
    detail = (await c.get(f"/v1/histories/{item['id']}", headers=auth("names"))).json()
    assert detail["start_place_name"] == "兒童探索博物館"
    assert detail["start_location"]["source"] == "open_data" and detail["end_location"] == detail["start_location"]
    assert detail["start_endpoint"]["type"] == "place_ref" and detail["start_endpoint"]["name"]
    assert detail["end_endpoint"] == detail["start_endpoint"]
    assert item.get("start_endpoint") is None
    assert item.get("start_location") is None


async def test_recheck_rules(env):
    c, ids, clock = env["client"], env["ids"], env["clock"]
    far = await c.post(
        "/v1/favorites",
        json={"conditions": cond(date="2026-10-30"), "stops": [{"place_id": str(ids["museum"])}]},
        headers={**auth(), "Idempotency-Key": v7()},
    )
    r = await c.post(f"/v1/favorites/{far.json()['favorite']['id']}/recheck", headers=auth())
    assert r.json() == {
        "rechecked": False,
        "reason": "OUTSIDE_EXTERNAL_COVERAGE",
        "message": r.json()["message"],
        "checked_at": None,
        "plan": None,
    }
    near = await c.post(
        "/v1/favorites",
        json={"conditions": cond(), "stops": [{"place_id": str(ids["museum"])}]},
        headers={**auth(), "Idempotency-Key": v7()},
    )
    r2 = await c.post(f"/v1/favorites/{near.json()['favorite']['id']}/recheck", headers=auth())
    assert r2.json()["rechecked"] is True and r2.json()["plan"]["mode"] == "manual"
    clock.now = datetime(2026, 10, 22, 2, 0, tzinfo=UTC)
    r3 = await c.post(f"/v1/favorites/{near.json()['favorite']['id']}/recheck", headers=auth())
    assert r3.json()["reason"] == "DEPARTURE_PASSED"


async def test_account_deletion_requires_recent_auth_and_old_token_cannot_recreate(env):
    c, st, clock = env["client"], env["st"], env["clock"]
    await c.post("/v1/trips/candidates", json={"query_id": v7(), "conditions": cond()}, headers=auth("del"))
    stale = await c.delete("/v1/me", headers={**auth("del", int(clock().timestamp()) - 600), "Idempotency-Key": v7()})
    assert stale.status_code == 401 and stale.json()["code"] == "REAUTH_REQUIRED"
    op = v7()
    ok = await c.delete("/v1/me", headers={**auth("del", int(clock().timestamp()) - 60), "Idempotency-Key": op})
    assert ok.status_code == 200 and ok.json()["status"] == "completed"
    assert await count(st, User) == 0 and await count(st, History) == 0
    assert await st.intents.is_completed(op)
    again = await c.get("/v1/me", headers=auth("del"))
    assert again.status_code == 401 and await count(st, User) == 0


async def test_cancel_registration_deletes_unverified_firebase_account_without_db_rows(env):
    c, st, clock = env["client"], env["st"], env["clock"]
    r = await c.delete("/v1/me/registration", headers=auth("unverified-cancel"))
    assert r.status_code == 204 and "unverified-cancel" in st.verifier.deleted
    assert await count(st, User) == 0 and await count(st, History) == 0
    again = await c.delete("/v1/me/registration", headers=auth("unverified-cancel"))
    assert again.status_code == 401
    member_delete = await c.delete(
        "/v1/me", headers={**auth("unverified-other", int(clock().timestamp()) - 60), "Idempotency-Key": v7()}
    )
    assert member_delete.status_code == 404 and member_delete.json()["code"] == "USER_NOT_FOUND"


async def test_cancel_registration_refuses_verified_accounts(env):
    c, st = env["client"], env["st"]
    assert (await c.get("/v1/me", headers=auth("member-1"))).status_code == 200
    r = await c.delete("/v1/me/registration", headers=auth("member-1"))
    assert r.status_code == 409 and r.json()["code"] == "REGISTRATION_COMPLETED"
    st.verifier.verified_later.add("unverified-late")
    late = await c.delete("/v1/me/registration", headers=auth("unverified-late"))
    assert late.status_code == 409 and late.json()["code"] == "REGISTRATION_COMPLETED"
    assert st.verifier.deleted == set() and await count(st, User, firebase_uid="member-1") == 1


async def test_purge_removes_only_unverified_registrations_older_than_24h(env):
    st, clock = env["st"], env["clock"]
    now_ms, hour = int(clock().timestamp() * 1000), 3600 * 1000
    st.verifier.accounts = {
        "unverified-old": now_ms - 25 * hour,
        "unverified-new": now_ms - hour,
        "unverified-unknown": None,
        "verified-old": now_ms - 48 * hour,
    }
    out = await purge_expired(st, clock())
    assert (out.removed, out.failures) == (1, 0) and st.verifier.deleted == {"unverified-old"}


async def test_guest_paid_rate_limit_and_problem_json(env):
    c = env["client"]
    codes = []
    for _ in range(6):
        r = await c.post("/v1/trips/candidates", json={"query_id": v7(), "conditions": cond()})
        codes.append(r.status_code)
    assert codes[:5] == [200] * 5 and codes[5] == 429
    assert r.headers["content-type"].startswith("application/problem+json") and r.json()["code"] == "RATE_LIMITED"


async def test_endpoint_select_limit_separate_and_session_cap(env):
    c = env["client"]
    tok = str(uuid.uuid4())
    for i in range(10):
        r = await c.post("/v1/endpoints/autocomplete", json={"input": "台北", "session_token": tok})
        assert r.status_code == 200, (i, r.text)
    r = await c.post("/v1/endpoints/autocomplete", json={"input": "台北", "session_token": tok})
    assert r.status_code == 429 and r.json()["code"] == "AUTOCOMPLETE_SESSION_LIMIT"
    sel = await c.post("/v1/endpoints/resolve", json={"google_place_id": "ChIJhome", "session_token": tok})
    assert sel.status_code == 200 and sel.json()["in_service_area"]
    r = await c.post("/v1/trips/candidates", json={"query_id": v7(), "conditions": cond()})
    assert r.status_code == 200
    short = await c.post("/v1/endpoints/autocomplete", json={"input": "台", "session_token": str(uuid.uuid4())})
    assert short.status_code == 422


async def test_app_check_enforced(env, tmp_path):
    import httpx
    from asgi_lifespan import LifespanManager

    from app.config import Settings
    from app.main import create_app

    st = env["st"]
    settings = Settings(
        env="test",
        database_url="x",
        app_check_enforce=True,
        deletion_intent_backend="local",
        deletion_intent_local_dir=str(tmp_path),
    )
    import dataclasses

    app = create_app(settings, lambda s: dataclasses.replace(st, settings=s))
    async with LifespanManager(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("10.9.9.9", 1)), base_url="http://t"
        ) as c:
            r = await c.post("/v1/trips/candidates", json={"query_id": v7(), "conditions": cond()})
            assert r.status_code == 403 and r.json()["code"] == "APP_CHECK_REQUIRED"
            r = await c.post(
                "/v1/trips/candidates",
                json={"query_id": v7(), "conditions": cond()},
                headers={"X-Firebase-AppCheck": "bad"},
            )
            assert r.status_code == 403 and r.json()["code"] == "APP_CHECK_FAILED"
            r = await c.post(
                "/v1/trips/candidates",
                json={"query_id": v7(), "conditions": cond()},
                headers={"X-Firebase-AppCheck": "ok"},
            )
            assert r.status_code == 200
