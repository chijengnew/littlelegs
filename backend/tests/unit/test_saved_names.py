import pytest

from app.api.v1.saved import endpoint_locations, endpoint_place_names

NAMES = {"0190a000-0000-7000-8000-000000000001": "兒童探索博物館", "0190a000-0000-7000-8000-000000000002": "親子旅店"}


def ref(pid: str) -> dict:
    return {"type": "place_ref", "place_id": pid}


def test_end_same_as_start_reuses_start_name():
    assert endpoint_place_names({"start": ref("0190a000-0000-7000-8000-000000000001"), "end": None}, NAMES) == (
        "兒童探索博物館",
        "兒童探索博物館",
    )


def test_separate_end_and_non_place_ref_endpoints():
    c = {
        "start": {"type": "device_coordinate", "lat": 25.0, "lng": 121.5},
        "end": ref("0190a000-0000-7000-8000-000000000002"),
    }
    assert endpoint_place_names(c, NAMES) == (None, "親子旅店")
    c = {"start": {"type": "google_place", "google_place_id": "ChIJhome"}, "end": None}
    assert endpoint_place_names(c, NAMES) == (None, None)


def test_unknown_or_removed_place_has_no_name():
    assert endpoint_place_names({"start": ref("0190a000-0000-7000-8000-00000000000f"), "end": None}, NAMES) == (
        None,
        None,
    )


@pytest.mark.anyio
async def test_endpoint_locations_device_and_google_without_db():

    device = {"type": "device_coordinate", "lat": 25.0, "lng": 121.5}
    loc = {"lat": 25.0, "lng": 121.5, "source": "device"}
    assert await endpoint_locations(None, {"start": device, "end": None}) == (loc, loc)  # type: ignore[arg-type]
    google = {"type": "google_place", "google_place_id": "ChIJhome"}
    assert await endpoint_locations(None, {"start": google, "end": device}) == (None, loc)  # type: ignore[arg-type]
    assert await endpoint_locations(None, {"start": google, "end": None}) == (None, None)  # type: ignore[arg-type]
