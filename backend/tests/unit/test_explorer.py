"""探險護照：蓋章輸入驗證、定位門檻、請求指紋與任務計算。"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.config import Stamping, get_settings
from app.domain import missions
from app.domain.missions import CountedPlace, Mission
from app.domain.stamping import CheckInIn, LocationIn, check_location, request_fingerprint
from app.errors import ApiError
from app.geo import haversine_m

PLACE = "0190a000-0000-7000-8000-000000000002"
OTHER = "0190a000-0000-7000-8000-000000000003"
SPOT = (25.03244, 121.5349)
RULES = Stamping()


def loc(lat: float = SPOT[0], lng: float = SPOT[1], accuracy_m: float = 20) -> dict:
    return {"lat": lat, "lng": lng, "accuracy_m": accuracy_m}


def test_location_request_requires_location():
    body = CheckInIn.model_validate({"place_id": PLACE, "verification_method": "location", "location": loc()})
    assert body.location is not None and body.location.accuracy_m == 20
    with pytest.raises(ValidationError):
        CheckInIn.model_validate({"place_id": PLACE, "verification_method": "location"})


def test_manual_request_rejects_location():
    assert CheckInIn.model_validate({"place_id": PLACE, "verification_method": "manual"}).location is None
    with pytest.raises(ValidationError):
        CheckInIn.model_validate({"place_id": PLACE, "verification_method": "manual", "location": loc()})


@pytest.mark.parametrize(
    "bad",
    [
        {"place_id": "not-a-uuid"},
        {"place_id": PLACE.upper()},
        {"verification_method": "gps"},
        {"location": loc(lat=91)},
        {"location": loc(lng=-181)},
        {"location": loc(accuracy_m=0)},
        {"location": loc(accuracy_m=-5)},
        {"location": loc(accuracy_m=100_001)},
        {"location": {"lat": "25.03", "lng": SPOT[1], "accuracy_m": 10}},
        {"location": {"lat": True, "lng": SPOT[1], "accuracy_m": 10}},
        {"location": {**loc(), "timestamp": 1}},
        {"extra": 1},
    ],
)
def test_invalid_requests_are_rejected(bad):
    body = {"place_id": PLACE, "verification_method": "location", "location": loc(), **bad}
    with pytest.raises(ValidationError):
        CheckInIn.model_validate(body)


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("field", ["lat", "lng", "accuracy_m"])
def test_nan_and_infinity_are_rejected(token, field):
    parts = {"lat": "25", "lng": "121.5", "accuracy_m": "10", field: token}
    location = ", ".join(f'"{k}": {v}' for k, v in parts.items())
    raw = f'{{"place_id": "{PLACE}", "verification_method": "location", "location": {{{location}}}}}'
    with pytest.raises(ValidationError):
        CheckInIn.model_validate(json.loads(raw))


def test_location_within_thresholds_passes():
    check_location(*SPOT, LocationIn(lat=SPOT[0] + 0.001, lng=SPOT[1], accuracy_m=100), RULES)


def test_inaccurate_location_is_rejected_before_distance():
    with pytest.raises(ApiError) as e:
        check_location(*SPOT, LocationIn(lat=SPOT[0], lng=SPOT[1], accuracy_m=100.5), RULES)
    assert e.value.code == "LOCATION_INACCURATE" and e.value.status == 422
    assert "100 公尺" in (e.value.detail or "")


def test_far_location_is_rejected_without_revealing_distance():
    lat = SPOT[0] + 0.0015
    d = haversine_m(lat, SPOT[1], *SPOT)
    assert 150 < d < 200
    with pytest.raises(ApiError) as e:
        check_location(*SPOT, LocationIn(lat=lat, lng=SPOT[1], accuracy_m=10), RULES)
    assert e.value.code == "LOCATION_TOO_FAR"
    assert str(round(d)) not in (e.value.detail or "") and not e.value.extra


def test_thresholds_are_configurable(monkeypatch):
    monkeypatch.setenv("STAMP_MAX_ACCURACY_M", "50")
    monkeypatch.setenv("STAMP_MAX_DISTANCE_M", "300")
    monkeypatch.setenv("LIMIT_UID_STAMP_PER_MIN", "4")
    get_settings.cache_clear()
    try:
        s = get_settings()
        assert (s.stamping.max_accuracy_m, s.stamping.max_distance_m, s.limits.uid_stamp_per_min) == (50, 300, 4)
        lat = SPOT[0] + 0.0015
        check_location(*SPOT, LocationIn(lat=lat, lng=SPOT[1], accuracy_m=40), s.stamping)
        with pytest.raises(ApiError):
            check_location(*SPOT, LocationIn(lat=lat, lng=SPOT[1], accuracy_m=60), s.stamping)
    finally:
        get_settings.cache_clear()


def test_fingerprint_covers_place_and_method_only():
    a = request_fingerprint(PLACE, "location")
    assert a == request_fingerprint(PLACE, "location") and len(a) == 32
    assert a != request_fingerprint(PLACE, "manual")
    assert a != request_fingerprint(OTHER, "location")


def test_mission_definitions_use_known_types():
    missions.validate(missions.MISSIONS)
    codes = [m.code for m in missions.MISSIONS]
    assert codes == ["first_stamp", "park_explorer", "culture_scholar", "little_explorer"]


@pytest.mark.parametrize(
    "bad",
    [
        [Mission("a", "distinct_places", 1), Mission("a", "distinct_places", 2)],
        [Mission("b", "distinct_cities", 1)],
        [Mission("c", "distinct_places", 0)],
        [Mission("d", "distinct_places", 1, ("playground",))],
        [Mission("Bad-Code", "distinct_places", 1)],
    ],
)
def test_invalid_mission_definitions_fail(bad):
    with pytest.raises(ValueError):
        missions.validate(bad)


def test_progress_counts_distinct_places_and_filters_types():
    places = [
        CountedPlace("p1", "park_playground"),
        CountedPlace("p1", "park_playground"),
        CountedPlace("p2", "museum"),
        CountedPlace("p3", "park_playground"),
        CountedPlace("p4", None),
    ]
    by = {m.code: missions.progress(m, places) for m in missions.MISSIONS}
    assert by == {"first_stamp": 4, "park_explorer": 2, "culture_scholar": 1, "little_explorer": 4}
    assert missions.progress(missions.MISSIONS[0], []) == 0
