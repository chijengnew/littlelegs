from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.domain.fingerprint import conditions_fingerprint, coord5, endpoint_identity, favorite_content_fingerprint
from app.domain.schemas import Conditions
from app.domain.validation import check_key_time, query_window_end
from app.errors import ApiError
from app.ids import is_canonical_uuid7, parse_uuid7, uuid7, uuid7_time


def test_uuid7_canonical_and_monotonic():
    ids = [uuid7() for _ in range(2000)]
    assert all(is_canonical_uuid7(str(u)) for u in ids)
    assert sorted(ids, key=lambda u: u.bytes) == ids
    assert sorted(ids, key=str) == ids
    assert uuid.UUID(bytes=ids[0].bytes) == ids[0]


@pytest.mark.parametrize(
    "bad",
    [
        "0190F3A0-0000-7000-8000-000000000000",
        "0190f3a000007000800000000000000",
        "{0190f3a0-0000-7000-8000-000000000000}",
        "0190f3a0-0000-4000-8000-000000000000",
    ],
)
def test_uuid7_rejects_noncanonical(bad):
    with pytest.raises(ValueError):
        parse_uuid7(bad)


def v7_at(dt: datetime) -> uuid.UUID:
    """測試用：直接組出指定時間的 UUIDv7（全域產生器刻意單調遞增，不能倒退）。"""
    ms = int(dt.timestamp() * 1000)
    return uuid.UUID(int=(ms << 80) | (0x7 << 76) | (0b10 << 62) | 12345)


def test_key_time_ahead_and_query_window():
    now = datetime(2026, 10, 20, 1, 0, tzinfo=UTC)
    ahead = v7_at(now + timedelta(hours=25))
    with pytest.raises(ApiError) as e:
        check_key_time(ahead, now)
    assert e.value.code == "KEY_TIME_INVALID"
    check_key_time(v7_at(now + timedelta(hours=23)), now)

    qid = v7_at(now)
    c = _cond(date(2026, 11, 18))
    end = query_window_end(qid, c)
    assert end > uuid7_time(qid) + timedelta(days=7)
    assert end == datetime(2026, 11, 18, 1, 0, tzinfo=UTC)
    near = _cond(date(2026, 10, 21))
    assert query_window_end(qid, near) == uuid7_time(qid) + timedelta(days=7)


def _cond(d: date, **kw) -> Conditions:
    base = {
        "date": d.isoformat(),
        "depart_time": "09:00",
        "return_time": "18:00",
        "start": {"type": "device_coordinate", "lat": 25.033, "lng": 121.565},
        "children_ages": [3],
    }
    base.update(kw)
    return Conditions.model_validate(base)


def test_coord5_half_up_and_negative_zero():
    assert coord5(25.123455) == "25.12346"
    assert coord5(25.123454) == "25.12345"
    assert coord5(-0.000001) == "0.00000"


def test_fingerprint_canonicalisation():
    a = _cond(date(2026, 10, 25), children_ages=[5, 3, 3], facility_prefs=["nursing_room", "family_toilet"])
    b = _cond(date(2026, 10, 25), children_ages=[3, 5, 3], facility_prefs=["family_toilet", "nursing_room"])
    c = _cond(date(2026, 10, 25), children_ages=[3, 5])
    ids = ("coord:25.03300,121.56500",) * 2
    assert conditions_fingerprint(a, *ids) == conditions_fingerprint(b, *ids)
    assert conditions_fingerprint(a, *ids) != conditions_fingerprint(c, *ids)


def test_label_not_in_fingerprint_and_place_id_case_preserved():
    a = _cond(date(2026, 10, 25), start={"type": "device_coordinate", "lat": 25.0, "lng": 121.5, "label": "家"})
    b = _cond(date(2026, 10, 25), start={"type": "device_coordinate", "lat": 25.0, "lng": 121.5, "label": "外婆家"})
    ida = endpoint_identity(a.start)
    assert ida == endpoint_identity(b.start)
    g1 = Conditions.model_validate(
        {**a.model_dump(mode="json"), "start": {"type": "google_place", "google_place_id": "ChIJabc"}}
    )
    g2 = Conditions.model_validate(
        {**a.model_dump(mode="json"), "start": {"type": "google_place", "google_place_id": "ChIJABC"}}
    )
    assert endpoint_identity(g1.start) != endpoint_identity(g2.start)


def test_favorite_fingerprint_depends_on_order_and_stay():
    c = _cond(date(2026, 10, 25))
    ids = ("s", "s")
    f1 = favorite_content_fingerprint(c, *ids, [("a", 60), ("b", 90)])
    f2 = favorite_content_fingerprint(c, *ids, [("b", 90), ("a", 60)])
    f3 = favorite_content_fingerprint(c, *ids, [("a", 75), ("b", 90)])
    assert len({f1, f2, f3}) == 3


def test_billing_month_window_follows_us_pacific_reset():
    from datetime import UTC, datetime

    from app.timeutil import billing_month_window_utc

    assert billing_month_window_utc(datetime(2026, 10, 20, 1, 0, tzinfo=UTC)) == (
        datetime(2026, 10, 1, 7, 0, tzinfo=UTC),
        datetime(2026, 11, 1, 7, 0, tzinfo=UTC),
    )
    start, _ = billing_month_window_utc(datetime(2026, 10, 31, 21, 0, tzinfo=UTC))
    assert start == datetime(2026, 10, 1, 7, 0, tzinfo=UTC)
    assert billing_month_window_utc(datetime(2026, 12, 15, tzinfo=UTC)) == (
        datetime(2026, 12, 1, 8, 0, tzinfo=UTC),
        datetime(2027, 1, 1, 8, 0, tzinfo=UTC),
    )


def test_http_client_request_urls_not_logged():
    import logging

    from app.logs import quiet_http_client_logs

    quiet_http_client_logs()
    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)
    assert not logging.getLogger("httpcore").isEnabledFor(logging.INFO)
