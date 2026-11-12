from app.domain.weather_areas import AreaPoint, district_of, group_points

TAIPEI_MAIN = (25.0478, 121.5170)
DAAN = (25.0263, 121.5436)
SHILIN = (25.0950, 121.5246)
JIUFEN = (25.1093, 121.8443)
YILAN = (24.7570, 121.7530)


def test_district_of_handles_three_address_styles():
    assert district_of("115 臺北市南港區研究院路二段128號") == "臺北市南港區"
    assert district_of("116臺北市文山區新光路二段30號") == "臺北市文山區"
    assert district_of("新北市石碇區碇格路一段") == "新北市石碇區"
    assert district_of("302新竹縣竹北市縣政九路") == "新竹縣竹北市"
    assert district_of("中山路一段1號", "臺南市") == "臺南市"
    assert district_of(None) is None


def test_close_points_share_one_area():
    areas = group_points([AreaPoint("start", *TAIPEI_MAIN), AreaPoint("a", *DAAN), AreaPoint("b", *SHILIN)])
    assert len(areas) == 1
    assert areas[0].keys == ["start", "a", "b"]


def test_far_points_get_their_own_area_and_label_is_most_common_district():
    areas = group_points(
        [
            AreaPoint("start", *TAIPEI_MAIN),
            AreaPoint("a", *DAAN, "臺北市大安區"),
            AreaPoint("b", *DAAN, "臺北市大安區"),
            AreaPoint("c", *TAIPEI_MAIN, "臺北市中正區"),
            AreaPoint("d", *JIUFEN, "新北市瑞芳區"),
            AreaPoint("end", *YILAN),
        ]
    )
    assert [a.keys for a in areas] == [["start", "a", "b", "c"], ["d"], ["end"]]
    assert [a.label for a in areas] == ["臺北市大安區", "新北市瑞芳區", None]


def test_at_most_six_areas_then_join_the_nearest():
    pts = [AreaPoint(str(i), 23.0 + i * 0.2, 121.0) for i in range(8)]
    areas = group_points(pts)
    assert len(areas) == 6
    assert areas[-1].keys == ["5", "6", "7"]


def _day(d: str, nxt: str, day_pct: int, night_pct: int) -> dict:
    def part(a: str, b: str, pct: int) -> dict:
        return {
            "interval": {"startTime": a, "endTime": b},
            "precipitation": {"probability": {"percent": pct, "type": "RAIN"}},
        }

    return {
        "daytimeForecast": part(f"{d}T07:00:00+08:00", f"{d}T19:00:00+08:00", day_pct),
        "nighttimeForecast": part(f"{d}T19:00:00+08:00", f"{nxt}T07:00:00+08:00", night_pct),
    }


class _Google:
    def __init__(self, by_lat: dict[float, int | None]) -> None:
        self.by_lat = by_lat
        self.calls: list[tuple[float, float]] = []

    async def daily_forecast(self, lat, lon, days, page_size, deadline):
        self.calls.append((lat, lon))
        pct = self.by_lat.get(lat)
        return None if pct is None else [_day("2026-11-13", "2026-11-14", pct, 5)]


def _run(by_lat: dict[float, int | None], rain: bool, trip: str = "2026-11-13"):
    import asyncio
    from datetime import date
    from types import SimpleNamespace

    from app.domain.schemas import Conditions
    from app.services.planning import _weather

    google = _Google(by_lat)
    ctx = SimpleNamespace(st=SimpleNamespace(google=google), today=date(2026, 11, 12), deadline=None)
    c = Conditions.model_validate(
        {
            "date": trip,
            "depart_time": "09:00",
            "return_time": "17:00",
            "start": {"type": "device_coordinate", "lat": TAIPEI_MAIN[0], "lng": TAIPEI_MAIN[1]},
            "children_ages": [4],
            "rain_indoor_only": rain,
        }
    )
    points = [
        AreaPoint("start", *TAIPEI_MAIN),
        AreaPoint("daan", *DAAN, "臺北市大安區"),
        AreaPoint("yilan", *YILAN, "宜蘭縣礁溪鄉"),
        AreaPoint("end", *TAIPEI_MAIN),
    ]
    return asyncio.run(_weather(ctx, c, points)), google


def test_weather_is_looked_up_per_area_even_without_rain_filter():
    from app.services.planning import _weather_out

    w, google = _run({TAIPEI_MAIN[0]: 10, YILAN[0]: 80}, rain=False)
    assert len(google.calls) == 2
    assert not w.triggered_for("yilan") and w.status_for("yilan") == "triggered"
    out = _weather_out(w)
    assert out is not None and out["status"] == "not_requested" and out["rain_filter"] is False
    assert [(a["label"], a["roles"], a["max_precipitation_percent"]) for a in out["areas"]] == [
        ("臺北市大安區", ["start", "end"], 10),
        ("宜蘭縣礁溪鄉", [], 80),
    ]
    assert out["parts"][0]["percent"] == 10


def test_rain_filter_judges_each_point_by_its_own_area():
    from app.services.planning import _weather_out

    w, _ = _run({TAIPEI_MAIN[0]: 10, YILAN[0]: 80}, rain=True)
    assert w.triggered_for("yilan") and not w.triggered_for("daan") and not w.triggered_for("start")
    assert _weather_out(w)["status"] == "triggered"
    assert _weather_out(w, [0])["status"] == "not_triggered"


def test_failed_area_is_dropped_without_rain_filter_but_unverified_with_it():
    from app.services.planning import _weather_out

    w, _ = _run({TAIPEI_MAIN[0]: 10, YILAN[0]: None}, rain=False)
    assert not w.external_failed and len(w.areas) == 1 and w.area_of("yilan") is None
    w2, _ = _run({TAIPEI_MAIN[0]: 10, YILAN[0]: None}, rain=True)
    assert w2.external_failed and w2.status_for("yilan") == "unverified"
    assert _weather_out(w2)["status"] == "unverified"


def test_beyond_ten_days_makes_no_call():
    w, google = _run({TAIPEI_MAIN[0]: 10}, rain=False, trip="2026-11-25")
    assert google.calls == [] and w.judgement is None and w.areas == []
    w2, google2 = _run({TAIPEI_MAIN[0]: 10}, rain=True, trip="2026-11-25")
    assert google2.calls == [] and w2.status_for("daan") == "unverified"
