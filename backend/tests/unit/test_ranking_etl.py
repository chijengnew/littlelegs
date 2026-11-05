from __future__ import annotations

from types import SimpleNamespace

from app.domain.ranking import (
    age_status,
    default_stay,
    evaluate,
    initial_rank_key,
    persistable_reasons,
    reasons_and_warnings,
    rerank_key,
)
from app.external.google import parse_matrix
from etl.lodging_facilities import extract, family_label
from etl.model import SourceRec
from etl.resolve import Cluster, address_level, merge, round_stay, tidy_name
from etl.sources import PARK_NAME, venue_name


def test_age_all_children_must_fit_discontinuous_not_merged():
    ranges = [(0, 2, "confirmed"), (6, 12, "confirmed")]
    assert age_status([1, 8], ranges, []) == "all_ok"
    assert age_status([1, 4], ranges, []) == "unsuitable"
    assert age_status([5], [], []) == "unknown"
    assert age_status([3, 7], [], [(0, 5)]) == "unsuitable"
    assert age_status([7], [(0, 12, "inferred")], []) == "unknown"


def test_persistable_reasons_drop_google_derived():
    r = ["age_match", "facility_match", "type_match", "nearby", "indoor_match"]
    assert persistable_reasons(r, "google") == ["age_match", "facility_match", "type_match"]
    assert "nearby" in persistable_reasons(r, "device") and "indoor_match" not in persistable_reasons(r, "device")


def test_matrix_parse_by_index_not_order_and_errors():
    data = [
        {
            "originIndex": 1,
            "destinationIndex": 0,
            "condition": "ROUTE_EXISTS",
            "duration": "600s",
            "distanceMeters": 5000,
        },
        {"destinationIndex": 1, "condition": "ROUTE_NOT_FOUND"},
        {"originIndex": 1, "destinationIndex": 1, "status": {"code": 13}},
    ]
    m = parse_matrix(data, 2)
    assert m[(1, 0)].status == "ok" and m[(1, 0)].seconds == 600
    assert m[(0, 1)].status == "no_route"
    assert m[(1, 1)].status == "unknown"
    assert m[(0, 0)].status == "unknown"


def test_lodging_facility_extraction():
    assert extract(None, "房內提供嬰兒床與嬰兒澡盆", None)["crib"].value == "yes"
    assert extract(None, "本館不提供嬰兒床", None)["crib"].value == "no"
    assert extract(None, "嬰兒床數量有限，需預約", None)["crib"].value == "unknown"
    assert "crib" not in extract(None, "提供嬰兒床圍", None)
    f = extract("無線網路,兒童遊樂設施", "", None)
    assert f["kids_play_area"].value == "yes" and family_label(f) == ["kids_play_area"]


def test_round_stay_and_venue_name():
    assert round_stay(30) == 30 and round_stay(37) == 30 and round_stay(38) == 45
    assert round_stay(500) == 360 and round_stay(5) == 15 and round_stay(0) is None
    assert venue_name("大安森林公園(署)") == "大安森林公園"
    assert venue_name("青年公園（1號）") == "青年公園"


def test_address_level():
    assert address_level(None) == 0 and address_level(" ") == 0
    assert address_level("臺北市中正區") == 1
    assert address_level("103 臺北市大同區") == 1
    assert address_level("花蓮縣秀林鄉富世村") == 1
    assert address_level("臺東縣卑南鄉杉原灣沙灘") == 2
    assert address_level("臺東縣臺東市豐田里博物館路一號") == 2
    assert address_level("宜蘭縣大同鄉太平巷58之1號") == 3


def test_merge_takes_most_complete_address_keeps_anchor_name_and_coords():
    def rec(ds, key, name, addr, lat=25.0):
        return SourceRec(ds, key, name, "attraction", address=addr, city="臺北市", lat=lat, lon=121.5)

    anchor = rec("tdx_attractions", "a", "大稻埕碼頭", "臺北市大同區")
    street = rec("taipei_attractions", "b", "大稻埕碼頭", "臺北市大同區民生西路底", lat=25.001)
    numbered = rec("tw_museums", "c", "大稻埕碼頭", "臺北市大同區民生西路1號", lat=25.002)
    m = merge(Cluster("attraction", [anchor, street, numbered]))
    assert m is not None
    assert (m.address, m.name, m.lat, m.coord_dataset) == (
        "臺北市大同區民生西路1號",
        "大稻埕碼頭",
        25.0,
        "tdx_attractions",
    )
    tie = merge(Cluster("attraction", [rec("tdx_attractions", "a", "某公園", "臺北市中正區甲路"), street]))
    assert tie is not None and tie.address == "臺北市中正區甲路"
    none = merge(Cluster("attraction", [rec("tdx_attractions", "a", "某公園", None)]))
    assert none is not None and none.address is None


def test_manifest_dates_accept_spreadsheet_formats():
    from datetime import date

    import pytest

    from etl.load_db import _date, _license_status, _source_updated

    assert _date("2026-10-16") == date(2026, 10, 16)
    assert _date("2026/10/16") == date(2026, 10, 16)
    assert _date("2026/8/3") == date(2026, 8, 3)
    assert _date("") is None
    with pytest.raises(ValueError):
        _date("10/16/2026")
    assert _source_updated("2026/8/3") == "2026-08-03"
    assert _source_updated("2026-10-16T02:30:03+08:00") == "2026-10-16T02:30:03+08:00"
    assert _license_status({"dataset_key": "x", "license_status": " Verified "}) == "verified"
    with pytest.raises(ValueError):
        _license_status({"dataset_key": "x", "license_status": "ok"})


def test_source_timestamps_output_as_iso():
    from app.services.places import iso_text

    assert iso_text("2026-06-25T11:17:59+08:00") == "2026-06-25T11:17:59+08:00"
    assert iso_text("2025-11-04 13:48:35 +08:00") == "2025-11-04T13:48:35+08:00"
    assert iso_text("2026-09-21 16:47:18") == "2026-09-21T16:47:18"
    assert iso_text("2026/09/02 15:29:20") == "2026-09-02T15:29:20"
    assert iso_text("2026-08-03") == "2026-08-03"
    assert iso_text("2026-01-02T03:04:05Z") == "2026-01-02T03:04:05+00:00"
    assert iso_text("2026-13-40") == "2026-13-40"
    assert iso_text("民國115年") == "民國115年"
    assert iso_text(None) is None


def test_candidate_rank_order_age_facility_type_distance_id():
    """偏好設施命中數 → 偏好類型 → 年齡分數換算後的距離 → 內部 ID。"""
    import uuid
    from types import SimpleNamespace

    def place(n, *, age_ok=False, facs=(), types=("other",)):
        return SimpleNamespace(
            id=uuid.UUID(int=n),
            age_ranges=[(0, 18, "confirmed")] if age_ok else [],
            age_exclusions=[],
            facilities={f: ("yes", "confirmed") for f in facs},
            types={t: "confirmed" for t in types},
            indoor=None,
            indoor_confirmation="unknown",
        )

    prefs = {"facility_prefs": ["nursing_room", "family_toilet"], "type_prefs": ["museum"]}
    evs = {
        "far_age_ok": evaluate(place(1, age_ok=True), 9000, [4], **prefs),
        "two_facs": evaluate(place(2, facs=("nursing_room", "family_toilet")), 5000, [4], **prefs),
        "one_fac_type": evaluate(place(3, facs=("nursing_room",), types=("museum",)), 4000, [4], **prefs),
        "one_fac": evaluate(place(4, facs=("nursing_room",)), 100, [4], **prefs),
        "type_only": evaluate(place(5, types=("museum",)), 3000, [4], **prefs),
        "near": evaluate(place(7), 200, [4], **prefs),
        "near_tie_low_id": evaluate(place(6), 200, [4], **prefs),
        "unchecked_fac": evaluate(place(8, facs=("stroller_friendly",)), 50, [4], **prefs),
    }
    expected = [
        "two_facs",
        "one_fac_type",
        "one_fac",
        "type_only",
        "far_age_ok",
        "unchecked_fac",
        "near_tie_low_id",
        "near",
    ]
    for key in (initial_rank_key, rerank_key):
        assert [k for k, _ in sorted(evs.items(), key=lambda kv: key(kv[1]))] == expected
    plain = [
        evaluate(place(n, facs=("nursing_room",), types=("museum",)), d, [4], [], []) for n, d in ((9, 300), (10, 100))
    ]
    assert [e.distance_m for e in sorted(plain, key=rerank_key)] == [100, 300]


def test_tidy_name_removes_underscores():
    assert tidy_name("北門_承恩門") == "北門承恩門"
    assert tidy_name("大屯山系_中正山步道") == "大屯山系中正山步道"
    assert tidy_name("關渡_金色水岸_八里左岸自行車道") == "關渡金色水岸八里左岸自行車道"
    assert tidy_name("大稻埕碼頭_大稻埕碼頭貨櫃市集") == "大稻埕碼頭貨櫃市集"
    assert tidy_name("北門＿承恩門(目前暫停開放)") == "北門承恩門(目前暫停開放)"
    assert tidy_name("太平山國家森林遊樂區") == "太平山國家森林遊樂區"
    assert tidy_name("_") == "_"
    assert tidy_name("臺中市長公館ˍ不老夢想125號") == "臺中市長公館不老夢想125號"


def test_tidy_name_removes_city_colon_prefix_only():
    assert tidy_name("台南：TJCOS台鉅美妝觀光工廠") == "TJCOS台鉅美妝觀光工廠"
    assert tidy_name("彰化:餅乾學院") == "餅乾學院"
    assert tidy_name("蟬說：霧繞") == "蟬說：霧繞"
    assert tidy_name("臺北市立動物園") == "臺北市立動物園"


def test_accept_decision_merges_cluster_even_when_target_comes_later():
    from etl.resolve import resolve

    a = SourceRec("tdx_attractions", "A", "民權公園", "attraction", city="臺北市", lat=25.0, lon=121.5)
    b = SourceRec("tdx_attractions", "B", "民權公園", "attraction", city="臺北市", lat=25.0006, lon=121.5)
    clusters, *_ = resolve([a, b], [], {})
    assert len(clusters) == 2
    clusters, *_ = resolve([a, b], [], {("tdx_attractions", "A"): ("accept", "tdx_attractions", "B")})
    assert len(clusters) == 1 and {m.source_key for m in clusters[0].members} == {"A", "B"}
    c = SourceRec("hsinchu_city_attractions", "C", "民權公園", "attraction", city="臺北市")
    clusters, _, excl, _ = resolve([a, b, c], [], {("tdx_attractions", "A"): ("accept", "tdx_attractions", "B")})
    assert len(clusters) == 1 and len(clusters[0].members) == 3 and not excl


def test_several_reject_decisions_for_one_record(tmp_path):
    from etl.resolve import load_decisions, load_rejections, resolve

    m = SourceRec("tw_museums", "M", "大溪木藝生態博物館", "attraction", city="桃園市", lat=24.88, lon=121.287)
    a = SourceRec(
        "tdx_attractions", "A", "大溪木藝生態博物館﹣藝師館", "attraction", city="桃園市", lat=24.88, lon=121.2870
    )
    b = SourceRec(
        "tdx_attractions", "B", "大溪木藝生態博物館﹣大溪歷史館", "attraction", city="桃園市", lat=24.8801, lon=121.287
    )
    p = tmp_path / "d.csv"
    head = "dataset_key,source_key,target_dataset_key,target_source_key,decision\n"
    p.write_text(
        head + "tw_museums,M,tdx_attractions,A,reject\ntw_museums,M,tdx_attractions,B,reject\n", encoding="utf-8"
    )
    _, reviews, _, _ = resolve([a, b, m], [], load_decisions(p), load_rejections(p))
    assert reviews == []
    _, reviews, _, _ = resolve([a, b, m], [], load_decisions(p))
    assert len(reviews) == 1


def test_park_name_required_for_tdx_park_classes():
    for n in ("大安森林公園", "美堤河濱公園", "共融遊戲場", "陽明山前山公園", "內湖文德濕地"):
        assert PARK_NAME.search(n), n
    for n in ("臺北賓館", "華山1914文化創意產業園區", "國立臺灣大學", "富錦街", "美堤碼頭"):
        assert not PARK_NAME.search(n), n


def test_name_override_replaces_display_name(tmp_path):
    from etl.resolve import load_name_overrides

    r = SourceRec("tdx_attractions", "K", "Oliven花藝工作室", "attraction", city="臺北市", lat=25.0, lon=121.5)
    p = tmp_path / "n.csv"
    p.write_text(
        "dataset_key,source_key,name,reason,decided_by\ntdx_attractions,K,新名稱花藝工作室,改名,人工\n",
        encoding="utf-8",
    )
    names = load_name_overrides(p)
    assert merge(Cluster("attraction", [r]), names).name == "新名稱花藝工作室"
    assert merge(Cluster("attraction", [r])).name == "Oliven花藝工作室"


def test_accept_decision_is_not_overwritten_by_later_reject(tmp_path):
    from etl.resolve import load_decisions

    p = tmp_path / "d.csv"
    head = "dataset_key,source_key,target_dataset_key,target_source_key,decision\n"
    p.write_text(head + "ds,K,ds,A,accept\nds,K,ds,B,reject\n", encoding="utf-8")
    assert load_decisions(p)[("ds", "K")] == ("accept", "ds", "A")


def _fit_place(primary_type, facs=()):
    import uuid
    from types import SimpleNamespace

    return SimpleNamespace(
        id=uuid.UUID(int=1),
        primary_type=primary_type,
        age_ranges=[],
        age_exclusions=[],
        facilities={f: ("yes", "confirmed") for f in facs},
        types={primary_type: "inferred"},
        indoor=None,
        indoor_confirmation="unknown",
    )


def test_every_place_type_has_a_contiguous_estimate_or_is_neutral():
    from app.domain.ranking import AGE_BANDS, TYPE_AGE_FIT
    from etl.model import PLACE_TYPES

    assert AGE_BANDS == ((0, 2), (3, 6), (7, 11), (12, 15), (16, 18))
    assert set(TYPE_AGE_FIT) <= set(PLACE_TYPES)
    assert set(PLACE_TYPES) - set(TYPE_AGE_FIT) == {
        "other",
        "temple",
        "community",
        "visitor_center",
        "station",
        "landmark",
    }
    for fit in TYPE_AGE_FIT.values():
        high = [i for i, s in enumerate(fit) if s == 2]
        assert high and high == list(range(high[0], high[-1] + 1))


def test_estimated_age_shows_range_and_all_children_must_be_inside_for_reason():
    prefs = {"facility_prefs": [], "type_prefs": []}
    ev = evaluate(_fit_place("parent_child_center"), 100, [1, 5], **prefs)
    assert (ev.age, ev.age_range, ev.age_match, ev.age_fit) == ("estimated", (0, 6), True, 2.0)
    older = evaluate(_fit_place("parent_child_center"), 100, [1, 9], **prefs)
    assert (older.age, older.age_match, older.age_fit) == ("estimated", False, 0.0)
    r, w = reasons_and_warnings(older, weather_status="not_requested", rain_checked=False)
    assert "age_match" not in r and "age_unknown" not in w
    r, _ = reasons_and_warnings(ev, weather_status="not_requested", rain_checked=False)
    assert "age_match" in r


def test_type_without_family_attribute_passes_without_range():
    ev = evaluate(_fit_place("other"), 100, [4], facility_prefs=[], type_prefs=[])
    assert (ev.age, ev.age_range, ev.age_match, ev.age_fit) == ("unknown", None, False, 1.0)
    _, w = reasons_and_warnings(ev, weather_status="not_requested", rain_checked=False)
    assert "age_unknown" not in w


def test_infant_facilities_raise_only_the_youngest_band_and_keep_range():
    p = _fit_place("museum", facs=("nursing_room",))
    plain = {"facility_prefs": [], "type_prefs": []}
    assert evaluate(p, 100, [1], **plain).age_fit == 0.5
    assert evaluate(_fit_place("museum"), 100, [1], **plain).age_fit == 0.0
    assert evaluate(_fit_place("museum", facs=("family_toilet",)), 100, [1], **plain).age_fit == 0.5
    assert evaluate(p, 100, [4], **plain).age_fit == 1.0
    assert evaluate(p, 100, [1], **plain).age_range == (7, 18)


def test_rank_weighs_age_fit_with_distance():
    plain = {"facility_prefs": [], "type_prefs": []}
    near_museum = evaluate(_fit_place("museum"), 2000, [4], **plain)
    far_park = evaluate(_fit_place("park_playground"), 25000, [4], **plain)
    close_park = evaluate(_fit_place("park_playground"), 6000, [4], **plain)
    for key in (initial_rank_key, rerank_key):
        assert sorted([far_park, near_museum], key=key)[0] is near_museum
        assert sorted([near_museum, close_park], key=key)[0] is close_park
    near_low = evaluate(_fit_place("museum"), 100, [1], **plain)
    far_high = evaluate(_fit_place("parent_child_center"), 20000, [1], **plain)
    assert sorted([far_high, near_low], key=rerank_key)[0] is near_low
    wanted = evaluate(_fit_place("museum"), 25000, [1], facility_prefs=[], type_prefs=["museum"])
    assert sorted([far_high, wanted], key=rerank_key)[0] is wanted


def test_default_stay_is_capped_but_user_override_is_not():
    long_source = SimpleNamespace(source_stay_minutes=300, primary_type="community")
    assert default_stay(long_source, None) == (120, "source")
    assert default_stay(long_source, 300) == (300, "user")
    short_source = SimpleNamespace(source_stay_minutes=30, primary_type="zoo")
    assert default_stay(short_source, None) == (30, "source")
    no_source = SimpleNamespace(source_stay_minutes=None, primary_type="amusement_park")
    assert default_stay(no_source, None) == (120, "type_default")
