"""回饋 API、過期清理與維運查詢。真實 MySQL＋FastAPI。"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Feedback, RateCounter
from app.ids import new_id
from app.services import feedback as svc

from .conftest import DB_URL, NOW

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

SECRET = "小明的聯絡內容-不可進日誌"
EMAIL = "parent-secret@example.com"


async def rows(st) -> list[Feedback]:
    async with st.factory() as s:
        return list((await s.execute(select(Feedback).order_by(Feedback.created_at))).scalars())


async def add(st, created_at, email=None) -> None:
    async with st.factory() as s, s.begin():
        s.add(
            Feedback(
                id=new_id(),
                type="other",
                rating=None,
                content="舊回饋",
                contact_email=email,
                source_page="other",
                place_id=None,
                created_at=created_at,
            )
        )


async def test_guest_feedback_stored_without_account_or_url(env):
    c, st = env["client"], env["st"]
    r = await c.post(
        "/v1/feedback",
        json={"type": "bug", "rating": 4, "content": SECRET, "contact_email": EMAIL, "source_page": "footer"},
    )
    assert r.status_code == 201 and r.json() == {"status": "received"}
    [f] = await rows(st)
    assert (f.type, f.rating, f.content, f.contact_email, f.source_page, f.place_id) == (
        "bug",
        4,
        SECRET,
        EMAIL,
        "footer",
        None,
    )
    assert not {c.name for c in Feedback.__table__.columns} & {"user_id", "uid", "url", "ip"}


async def test_member_feedback_not_linked_and_invalid_token_does_not_block(env):
    c, st = env["client"], env["st"]
    r = await c.post("/v1/feedback", json={"type": "other", "content": "會員"}, headers={"Authorization": "Bearer bad"})
    assert r.status_code == 201
    assert len(await rows(st)) == 1


async def test_place_report_keeps_internal_place_id_only_when_place_exists(env, seeded):
    c, st = env["client"], env["st"]
    place = str(seeded["museum"])
    ok = await c.post(
        "/v1/feedback",
        json={"type": "place_data", "content": "地址錯了", "source_page": "place_detail", "place_id": place},
    )
    assert ok.status_code == 201
    [f] = await rows(st)
    assert str(f.place_id) == place
    missing = await c.post(
        "/v1/feedback",
        json={"type": "place_data", "content": "x", "place_id": "0190a000-0000-7000-8000-00000000ffff"},
    )
    assert missing.status_code == 422 and missing.json()["code"] == "PLACE_NOT_FOUND"
    wrong_type = await c.post("/v1/feedback", json={"type": "bug", "content": "x", "place_id": place})
    assert wrong_type.status_code == 422


async def test_validation_error_does_not_echo_input(env):
    c = env["client"]
    r = await c.post("/v1/feedback", json={"type": "bug", "content": SECRET, "contact_email": "secret-not-an-email"})
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_FAILED"
    assert "secret-not-an-email" not in r.text and SECRET not in r.text


async def test_content_and_email_not_written_to_logs(env, caplog):
    caplog.set_level(logging.DEBUG)
    r = await env["client"].post("/v1/feedback", json={"type": "bug", "content": SECRET, "contact_email": EMAIL})
    assert r.status_code == 201
    assert SECRET not in caplog.text and EMAIL not in caplog.text


async def test_rate_limit_three_per_minute_and_counts_towards_global(env):
    c, st = env["client"], env["st"]
    codes = [(await c.post("/v1/feedback", json={"type": "other", "content": "x"})).status_code for _ in range(3)]
    assert codes == [201, 201, 201]
    r = await c.post("/v1/feedback", json={"type": "other", "content": "x"})
    assert r.status_code == 429 and r.json()["code"] == "RATE_LIMITED"
    assert r.headers["content-type"].startswith("application/problem+json")
    assert len(await rows(st)) == 3
    async with st.factory() as s:
        keys = set((await s.execute(select(RateCounter.counter_key))).scalars())
    assert any(k.endswith(":feedback") for k in keys) and any(k.endswith(":all") for k in keys)
    other = await c.post("/v1/endpoints/places/search", json={"q": "博物館"})
    assert other.status_code == 200


async def test_app_check_required_when_enforced(env, monkeypatch):
    c, st = env["client"], env["st"]
    monkeypatch.setattr(st, "settings", replace(st.settings, app_check_enforce=True))
    r = await c.post("/v1/feedback", json={"type": "other", "content": "x"})
    assert r.status_code == 403 and r.json()["code"] == "APP_CHECK_REQUIRED"
    assert await rows(st) == []


async def test_purge_only_after_retention(env):
    st = env["st"]
    await add(st, NOW - svc.RETENTION - timedelta(seconds=1))
    await add(st, NOW - svc.RETENTION + timedelta(seconds=1))
    await add(st, NOW)
    assert await svc.purge_expired(st.factory, NOW) == 1
    assert len(await rows(st)) == 2
    assert await svc.purge_expired(st.factory, NOW) == 0


async def test_maintenance_job_cleans_expired_feedback(env, monkeypatch):
    from scripts import maintenance

    st = env["st"]
    await add(st, NOW - svc.RETENTION - timedelta(days=1))
    eng = create_async_engine(DB_URL, connect_args={"init_command": "SET time_zone = '+00:00'"})
    monkeypatch.setattr(maintenance, "db", lambda: (None, eng, async_sessionmaker(eng, expire_on_commit=False)))
    result = await maintenance.run()
    assert result["feedback"] == 1
    async with st.factory() as s:
        assert (await s.execute(select(func.count()).select_from(Feedback))).scalar() == 0


async def test_find_by_email_and_delete_for_personal_data_requests(env):
    st = env["st"]
    await add(st, NOW, email=EMAIL)
    await add(st, NOW + timedelta(seconds=1), email="other@example.com")
    found = await svc.find(st.factory, email=EMAIL)
    assert [x.contact_email for x in found] == [EMAIL]
    assert await svc.delete_one(st.factory, found[0].id) is True
    assert await svc.delete_one(st.factory, found[0].id) is False
    assert await svc.find(st.factory, email=EMAIL) == []
    assert len(await rows(st)) == 1
