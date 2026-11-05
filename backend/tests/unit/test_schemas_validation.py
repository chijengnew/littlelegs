from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.schemas import Conditions, PlanIn
from app.domain.validation import check_departure_future, check_new_search_date
from app.errors import ApiError

NOW = datetime(2026, 10, 20, 1, 0, tzinfo=UTC)
START = {"type": "device_coordinate", "lat": 25.03, "lng": 121.56}


def c(**kw):
    base = {"date": "2026-10-25", "depart_time": "09:00", "return_time": "18:00", "start": START, "children_ages": [4]}
    base.update(kw)
    return Conditions.model_validate(base)


@pytest.mark.parametrize(
    "kw",
    [
        {"children_ages": []},
        {"children_ages": [1, 2, 3, 4, 5, 6]},
        {"children_ages": [19]},
        {"children_ages": [-1]},
        {"depart_time": "09:10"},
        {"return_time": "10:45"},
        {"nap": {"start": "08:00", "end": "09:30"}},
        {"nap": {"start": "13:00", "end": "13:00"}},
        {"lunch": {"start": "12:00", "end": "12:45"}},
        {"travel_mode": "transit"},
        {"unknown_field": 1},
    ],
)
def test_conditions_invalid(kw):
    with pytest.raises(ValidationError):
        c(**kw)


def test_conditions_valid_edges():
    x = c(
        children_ages=[0, 18, 18],
        depart_time="09:00",
        return_time="11:00",
        nap={"start": "09:00", "end": "11:00"},
        lunch={"start": "10:00", "end": "11:00"},
    )
    assert x.children_ages == [0, 18, 18]


def test_stops_unique_and_bounds():
    base = {"query_id": "019a0000-0000-7000-8000-000000000001", "conditions": c().model_dump(mode="json")}
    pid = "019a0000-0000-7000-8000-0000000000aa"
    with pytest.raises(ValidationError):
        PlanIn.model_validate({**base, "stops": [{"place_id": pid}, {"place_id": pid}]})
    with pytest.raises(ValidationError):
        PlanIn.model_validate({**base, "stops": []})
    with pytest.raises(ValidationError):
        PlanIn.model_validate({**base, "stops": [{"place_id": pid, "stay_minutes": 70}]})
    with pytest.raises(ValidationError):
        PlanIn.model_validate({**base, "stops": [{"place_id": pid, "stay_minutes": 375}]})
    six = [{"place_id": f"019a0000-0000-7000-8000-00000000000{i}"} for i in range(6)]
    with pytest.raises(ValidationError):
        PlanIn.model_validate({**base, "stops": six})


@pytest.mark.parametrize(
    "d,ok", [("2026-10-19", False), ("2026-10-20", True), ("2026-11-18", True), ("2026-11-19", False)]
)
def test_date_range_d_to_d29(d, ok):
    if ok:
        check_new_search_date(c(date=d), NOW)
    else:
        with pytest.raises(ApiError) as e:
            check_new_search_date(c(date=d), NOW)
        assert e.value.status == 422


def test_departure_passed_same_day():
    with pytest.raises(ApiError) as e:
        check_departure_future(c(date="2026-10-20", depart_time="09:00", return_time="12:00"), NOW)
    assert (e.value.status, e.value.code) == (409, "DEPARTURE_PASSED")
    check_departure_future(c(date="2026-10-20", depart_time="09:15", return_time="12:00"), NOW)


def test_openapi_documents_problem_json_errors():
    from app.main import create_app

    doc = create_app().openapi()
    assert "HTTPValidationError" not in doc["components"]["schemas"]
    for item in doc["paths"].values():
        for op in item.values():
            for status, resp in op["responses"].items():
                if status[0] in "45":
                    assert list(resp["content"]) == ["application/problem+json"]
    responses = doc["paths"]["/v1/trips/candidates"]["post"]["responses"]
    assert {"401", "403", "409", "422", "429", "500", "503"} <= set(responses)
    assert "404" in doc["paths"]["/v1/places/{place_id}"]["get"]["responses"]
    assert "202" in doc["paths"]["/v1/me"]["delete"]["responses"]
    ex = responses["409"]["content"]["application/problem+json"]["example"]
    assert ex["code"] == "DEPARTURE_PASSED" and ex["status"] == 409
    place_404 = doc["paths"]["/v1/places/{place_id}"]["get"]["responses"]["404"]
    assert place_404["content"]["application/problem+json"]["example"]["code"] == "PLACE_NOT_FOUND"
    for path in ("/v1/me", "/v1/histories", "/v1/favorites"):
        forbidden = doc["paths"][path]["get"]["responses"]["403"]
        assert forbidden["content"]["application/problem+json"]["example"]["code"] == "EMAIL_NOT_VERIFIED", path


def test_violation_codes_documented():
    """排程與規劃程式產生的違規代碼都要列在回應模型裡，否則回應驗證會失敗。"""
    import re
    from pathlib import Path
    from typing import get_args

    from app.api.v1.models import ViolationCode

    pattern = re.compile(r'(?:"code":\s*|codes\.append\(|viol\.add\(|hard\.add\(|codes, details = \[)"([A-Z_]+)"')
    root = Path(__file__).resolve().parents[2] / "app"
    found = set()
    for f in (root / "domain" / "scheduler.py", root / "services" / "planning.py"):
        found |= set(pattern.findall(f.read_text(encoding="utf-8")))
    assert len(found) >= 10
    assert found <= set(get_args(ViolationCode)), found - set(get_args(ViolationCode))
