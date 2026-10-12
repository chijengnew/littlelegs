from fastapi.testclient import TestClient

from main import app

client = TestClient(app)
LUCA = {"Authorization": "Bearer mock:luca"}
AMY = {"Authorization": "Bearer mock:amy"}


def make_conditions(**parent_overrides):
    parent = {
        "county": "taipei",
        "date": "2026-10-17",
        "startTime": "09:00",
        "availableMinutes": 240,
        "transport": "car",
        "needStroller": True,
        "needNursingRoom": False,
        "preferIndoor": False,
    }
    parent.update(parent_overrides)
    return {
        "child": {"ages": [3, 6], "napStart": "13:00", "napEnd": "14:30", "lunchTime": "12:00"},
        "parent": parent,
    }


def recommend(**parent_overrides):
    return client.post("/api/recommendations", json=make_conditions(**parent_overrides))


def plan(place_ids, **parent_overrides):
    body = {"conditions": make_conditions(**parent_overrides), "placeIds": place_ids}
    return client.post("/api/itineraries/plan", json=body)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_recommendations_only_selected_county_sorted_by_score():
    body = recommend().json()
    assert [item["place"]["id"] for item in body["results"]] == [
        "tp-children-park",
        "tp-zoo",
        "tp-daan-park",
        "tp-science-edu",
    ]
    scores = [item["score"] for item in body["results"]]
    assert scores == sorted(scores, reverse=True)


def test_closed_weekday_is_filtered_out():
    ids = {item["place"]["id"] for item in recommend(date="2026-10-19").json()["results"]}
    assert ids == {"tp-zoo", "tp-daan-park"}


def test_place_longer_than_available_time_is_filtered_out():
    ids = {item["place"]["id"] for item in recommend(availableMinutes=120).json()["results"]}
    assert ids == {"tp-daan-park", "tp-science-edu"}


def test_rain_puts_indoor_place_first():
    body = recommend(date="2026-10-20").json()
    assert body["weather"]["summary"] == "rain"
    assert body["results"][0]["place"]["id"] == "tp-science-edu"


def test_invalid_input_returns_422():
    assert recommend(startTime="25:00").status_code == 422
    assert recommend(availableMinutes=30).status_code == 422


def test_plan_single_stop():
    body = plan(["tp-zoo"]).json()
    assert body["feasible"] is True
    assert body["usedMinutes"] == 180
    assert body["notes"][0]["code"] == "single_stop"


def test_plan_order_does_not_depend_on_click_order():
    first = plan(["tp-science-edu", "tp-daan-park"]).json()
    second = plan(["tp-daan-park", "tp-science-edu"]).json()
    assert first == second
    assert [stop["place"]["id"] for stop in first["stops"]] == ["tp-daan-park", "tp-science-edu"]


def test_plan_over_time_is_rejected():
    body = plan(["tp-zoo", "tp-daan-park"]).json()
    assert body["feasible"] is False
    assert body["reason"] == {"code": "over_time", "params": {"used": 265, "available": 240}}


def test_plan_invalid_place_ids():
    assert plan(["tp-zoo", "a", "b", "c", "d", "e"]).json()["reason"]["code"] == "too_many"
    assert plan(["nope"]).json()["reason"]["code"] == "unknown_place"
    assert plan([]).status_code == 422


def test_member_api_requires_login():
    assert client.get("/api/me/history").status_code == 401
    assert client.get("/api/me/favorites").status_code == 401
    assert client.get("/api/me/history", headers={"Authorization": "Bearer abc"}).status_code == 401


def test_history_flow():
    record = recommend().json()
    first = client.post("/api/me/history", json=record, headers=LUCA)
    second = client.post("/api/me/history", json=record, headers=LUCA)
    assert first.status_code == 201
    assert first.json()["createdAt"] == second.json()["createdAt"]

    luca_ids = [item["queryId"] for item in client.get("/api/me/history", headers=LUCA).json()]
    amy_ids = [item["queryId"] for item in client.get("/api/me/history", headers=AMY).json()]
    assert luca_ids.count(record["queryId"]) == 1
    assert record["queryId"] not in amy_ids

    path = f"/api/me/history/{record['queryId']}"
    assert client.delete(path, headers=AMY).status_code == 404
    assert client.delete(path, headers=LUCA).status_code == 204
    assert client.delete(path, headers=LUCA).status_code == 404


def test_favorite_flow():
    feasible = plan(["tp-daan-park", "tp-science-edu"]).json()
    saved = client.post("/api/me/favorites", json={"conditions": make_conditions(), "itinerary": feasible}, headers=LUCA)
    assert saved.status_code == 201
    favorite_id = saved.json()["id"]

    infeasible = plan(["tp-zoo", "tp-daan-park"]).json()
    rejected = client.post("/api/me/favorites", json={"conditions": make_conditions(), "itinerary": infeasible}, headers=LUCA)
    assert rejected.status_code == 422

    assert any(item["id"] == favorite_id for item in client.get("/api/me/favorites", headers=LUCA).json())
    assert client.delete(f"/api/me/favorites/{favorite_id}", headers=AMY).status_code == 404
    assert client.delete(f"/api/me/favorites/{favorite_id}", headers=LUCA).status_code == 204