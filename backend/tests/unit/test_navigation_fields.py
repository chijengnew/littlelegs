"""導航連結用的欄位：只給查核接受的 Place ID；裝置座標回傳使用者自己的條件。"""

from __future__ import annotations

from app.services.endpoints import ResolvedEndpoint
from app.services.places import reliable_place_id
from app.services.planning import _endpoint_out


def test_only_accepted_place_id_is_reliable():
    assert reliable_place_id("ChIJa", "accepted") == "ChIJa"
    assert reliable_place_id("ChIJa", "pending") is None
    assert reliable_place_id(None, "accepted") is None


def test_place_ref_endpoint_has_name_address_and_id_for_guest():
    r = ResolvedEndpoint(
        "place_ref",
        25.0,
        121.5,
        "open_data",
        place_ref="p",
        google_place_id="ChIJa",
        place_name="某地",
        place_address="臺北市",
    )
    d = _endpoint_out(r, member=False)
    assert (d["name"], d["address"], d["google_place_id"]) == ("某地", "臺北市", "ChIJa")
    assert "location" not in d


def test_device_coordinate_returns_own_condition_for_guest():
    d = _endpoint_out(ResolvedEndpoint("device_coordinate", 25.0, 121.5, "device"), member=False)
    assert d["coordinate"] == {"lat": 25.0, "lng": 121.5}
    assert "location" not in d


def test_google_place_endpoint_keeps_place_id_and_label():
    r = ResolvedEndpoint("google_place", 25.0, 121.5, "google", google_place_id="ChIJh", label="家")
    d = _endpoint_out(r, member=False)
    assert (d["google_place_id"], d["label"]) == ("ChIJh", "家")
