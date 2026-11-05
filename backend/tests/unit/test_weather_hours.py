from __future__ import annotations

from datetime import date, time

import pytest

from app.domain.hours import opening_for_date
from app.domain.weather import judge, request_params

TODAY = date(2026, 10, 20)


def day(d: date, day_pct, night_pct, ptype="RAIN"):
    def part(start, end, pct):
        prob = {} if pct is None else {"percent": pct, "type": ptype}
        return {"interval": {"startTime": start, "endTime": end}, "precipitation": {"probability": prob}}

    nd = date.fromordinal(d.toordinal() + 1)
    return {
        "displayDate": {"year": d.year, "month": d.month, "day": d.day},
        "daytimeForecast": part(f"{d}T07:00:00+08:00", f"{d}T19:00:00+08:00", day_pct),
        "nighttimeForecast": part(f"{d}T19:00:00+08:00", f"{nd}T07:00:00+08:00", night_pct),
    }


@pytest.mark.parametrize(
    "pct,status", [(0, "not_triggered"), (59, "not_triggered"), (60, "triggered"), (100, "triggered")]
)
def test_threshold(pct, status):
    d = date(2026, 10, 22)
    j = judge([day(date(2026, 10, 21), 0, 0), day(d, pct, 0)], d, time(9), time(18))
    assert j.status == status


def test_snow_type_counts_as_precipitation():
    d = date(2026, 10, 22)
    assert judge([day(d, 70, 0, "SNOW")], d, time(9), time(18)).status == "triggered"


def test_missing_field_is_unknown_not_zero():
    d = date(2026, 10, 22)
    j = judge([day(d, None, 0)], d, time(9), time(18))
    assert j.status == "unverified" and j.uncovered


def test_depart_before_7_needs_previous_night():
    d = date(2026, 10, 22)
    j = judge([day(date(2026, 10, 21), 0, 80), day(d, 10, 10)], d, time(6), time(18))
    assert j.status == "triggered" and j.max_percent == 80


def test_return_after_19_uses_night():
    d = date(2026, 10, 22)
    j = judge([day(date(2026, 10, 21), 0, 0), day(d, 10, 65)], d, time(9), time(20))
    assert j.status == "triggered"


def test_today_early_morning_uncovered():
    j = judge([day(TODAY, 10, 10)], TODAY, time(6), time(18))
    assert j.status == "unverified"
    assert j.uncovered[0][1].hour == 7


def test_partial_missing_but_other_part_triggers():
    d = date(2026, 10, 22)
    j = judge([day(d, 75, None)], d, time(9), time(21))
    assert j.status == "triggered"


@pytest.mark.parametrize(
    "off,params", [(0, {"days": 1, "pageSize": 10}), (9, {"days": 10, "pageSize": 10}), (10, None)]
)
def test_forecast_window(off, params):
    assert request_params(date.fromordinal(TODAY.toordinal() + off), TODAY) == params


def cur_period(d: date, oh, ch, cday=None):
    cd = cday or d
    return {
        "open": {
            "day": (d.weekday() + 1) % 7,
            "hour": oh,
            "minute": 0,
            "date": {"year": d.year, "month": d.month, "day": d.day},
        },
        "close": {
            "day": (cd.weekday() + 1) % 7,
            "hour": ch,
            "minute": 0,
            "date": {"year": cd.year, "month": cd.month, "day": cd.day},
        },
    }


def test_current_hours_known_within_d6():
    d = date(2026, 10, 26)
    info = opening_for_date(
        {"businessStatus": "OPERATIONAL", "currentOpeningHours": {"periods": [cur_period(d, 9, 17)]}}, d, TODAY
    )
    assert info.status == "known" and info.intervals[0][0].hour == 9


def test_d7_uses_regular_as_provisional():
    d = date(2026, 10, 27)
    place = {
        "businessStatus": "OPERATIONAL",
        "currentOpeningHours": {"periods": [cur_period(d, 9, 17)]},
        "regularOpeningHours": {
            "periods": [{"open": {"day": 2, "hour": 10, "minute": 0}, "close": {"day": 2, "hour": 16, "minute": 0}}]
        },
    }
    info = opening_for_date(place, d, TODAY)
    assert info.status == "provisional" and info.intervals[0][0].hour == 10


def test_explicit_empty_periods_means_closed_not_unknown():
    d = date(2026, 10, 21)
    info = opening_for_date({"businessStatus": "OPERATIONAL", "currentOpeningHours": {"periods": []}}, d, TODAY)
    assert info.status == "known" and info.intervals == []


def test_missing_hours_unknown():
    assert opening_for_date({"businessStatus": "OPERATIONAL"}, date(2026, 10, 21), TODAY).status == "unknown"
    assert opening_for_date(None, date(2026, 10, 21), TODAY).status == "unknown"


def test_cross_midnight_regular():
    d = date(2026, 10, 28)
    place = {
        "regularOpeningHours": {
            "periods": [{"open": {"day": 2, "hour": 20, "minute": 0}, "close": {"day": 3, "hour": 2, "minute": 0}}]
        }
    }
    info = opening_for_date(place, d, TODAY)
    assert [(a.hour, b.hour) for a, b in info.intervals] == [(0, 2)]


def test_always_open_any_weekday():
    place = {"regularOpeningHours": {"periods": [{"open": {"day": 0, "hour": 0, "minute": 0}}]}}
    for off in range(7, 14):
        d = date.fromordinal(TODAY.toordinal() + off)
        info = opening_for_date(place, d, TODAY)
        assert info.status == "provisional" and len(info.intervals) == 1


@pytest.mark.parametrize(
    "bs,status", [("CLOSED_PERMANENTLY", "closed_permanently"), ("CLOSED_TEMPORARILY", "closed_temporarily")]
)
def test_business_status(bs, status):
    assert opening_for_date({"businessStatus": bs}, date(2026, 10, 21), TODAY).status == status
