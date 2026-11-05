"""Place ID 自動配對規則與名稱／門牌比對鍵。"""

from __future__ import annotations

from types import SimpleNamespace

from app.textnorm import house_number_key, name_key
from scripts.place_ids import judge

PLACE = SimpleNamespace(name="太平山國家森林遊樂區", address="宜蘭縣大同鄉太平巷58之1號", lat=24.557468, lon=121.4995)


def g(pid, name, lat, lon, addr=""):
    return {
        "id": pid,
        "displayName": {"text": name},
        "location": {"latitude": lat, "longitude": lon},
        "formattedAddress": addr,
    }


def test_name_key_unifies_simplified_and_tai():
    assert name_key("太平山国家森林游乐区") == name_key("太平山國家森林遊樂區")
    assert name_key("台北市立動物園") == name_key("臺北市立動物園")
    assert name_key("霧峯林家") == name_key("霧峰林家")
    assert name_key("國立 臺灣美術館") == name_key("國立臺灣美術館")
    assert name_key("糖果工廠") != name_key("糖果觀光工廠")
    assert name_key("臺北：二二八和平公園") == name_key("二二八和平公園")
    assert name_key("台中:審計新村") == name_key("審計新村")


def test_name_key_ignores_admin_prefixes():
    assert name_key("新竹市玻璃工藝博物館") == name_key("玻璃工藝博物館")
    assert name_key("國立臺灣博物館") == name_key("臺灣博物館")
    assert name_key("新北市立黃金博物館") == name_key("黃金博物館")
    assert name_key("臺北市立動物園") == name_key("台北市立動物園")
    assert name_key("臺中市場") != name_key("場")
    assert name_key("新竹市") == name_key("新竹市")


def test_house_number_key():
    assert house_number_key("宜蘭縣大同鄉太平巷58之1號") == "太平巷58之1號"
    assert house_number_key("267宜兰县大同乡太平村太平巷58之1號") == "太平巷58之1號"
    assert house_number_key("臺北市中正區黎明里5鄰中山南路21號") == house_number_key("100台北市中正區中山南路21號3樓")
    assert house_number_key("新北市三峽區有木里有木174-1號") == house_number_key("新北市三峽區有木里有木174之1號")
    assert house_number_key("臺北市中山路1號") != house_number_key("臺北市中正路1號")
    assert house_number_key("金門縣金沙鎮山后民俗文化村") is None


def test_same_name_and_house_number_accepts_regardless_of_distance():
    res = [
        g("A", "太平山國家森林遊樂區", 24.50, 121.53, "267宜兰县大同乡太平村太平巷58之1號"),
        g("B", "太平山國家公園", 24.50, 121.53, "267宜兰县大同乡太平村太平巷58之1號"),
    ]
    assert judge(PLACE, res) == ("A", ["A", "B"], "自動接受：同名且門牌相同")


def test_same_name_unique_within_1km_accepts():
    res = [g("A", "太平山国家森林游乐区", 24.5620, 121.4995)]
    assert judge(PLACE, res)[0] == "A"


def test_two_same_name_within_1km_needs_review():
    res = [g("A", "太平山國家森林遊樂區", 24.5620, 121.4995), g("B", "太平山國家森林遊樂區", 24.5610, 121.5010)]
    auto, _, reason = judge(PLACE, res)
    assert auto is None and reason == "多個同名（2 筆）"


def test_one_within_100m_still_accepted_with_far_duplicate():
    res = [g("A", "太平山國家森林遊樂區", 24.5576, 121.4996), g("B", "太平山國家森林遊樂區", 24.5640, 121.4995)]
    assert judge(PLACE, res)[0] == "A"


def test_rules_pointing_to_different_places_need_review():
    res = [
        g("A", "太平山國家森林遊樂區", 24.5620, 121.4995, "宜蘭縣大同鄉某路1號"),
        g("B", "太平山國家森林遊樂區", 24.50, 121.53, "宜蘭縣大同鄉太平巷58之1號"),
    ]
    auto, _, reason = judge(PLACE, res)
    assert auto is None and reason == "多個同名，距離與門牌指向不同地點"


def test_review_reasons():
    assert judge(PLACE, []) == (None, [], "Google 查無結果")
    assert judge(PLACE, [g("A", "太平山莊", 24.5576, 121.4995)])[2] == "名稱不同（Google 前 1 筆皆不同名）"
    far = [g("A", "太平山國家森林遊樂區", 24.50, 121.53, "宜蘭縣大同鄉另一路9號")]
    reason = judge(PLACE, far)[2]
    assert reason == "同名但距離 >1 km，且門牌不同"
    assert not any(ch.isdigit() for ch in reason.replace(">1 km", ""))


def test_contained_name_with_same_house_number_or_within_100m_accepts():
    p = SimpleNamespace(name="海印寺", address="金門縣金湖鎮海印寺1號", lat=24.4400, lon=118.4200)
    far_same_house = [g("A", "太武山海印寺", 24.46, 118.42, "891金門縣金湖鎮海印寺1號")]
    assert judge(p, far_same_house) == ("A", ["A"], "自動接受：Google 名稱包含來源名稱且門牌相同，且只有一筆")
    near = [g("A", "太武山海印寺", 24.4405, 118.4200)]
    assert judge(p, near)[2] == "自動接受：Google 名稱包含來源名稱且100 m 內，且只有一筆"


def test_contained_name_needs_review_when_far_ambiguous_or_too_short():
    p = SimpleNamespace(name="海印寺", address="金門縣金湖鎮海印寺1號", lat=24.4400, lon=118.4200)
    far = [g("A", "太武山海印寺", 24.46, 118.42, "金門縣金湖鎮另一路2號")]
    assert judge(p, far) == (None, ["A"], "Google 名稱包含來源名稱但距離 >100 m，且門牌不同")
    two = [g("A", "太武山海印寺", 24.4405, 118.42), g("B", "海印寺停車場", 24.4401, 118.42)]
    assert judge(p, two)[2] == "多個 Google 名稱包含來源名稱的候選（2 筆）符合門牌或距離"
    short = SimpleNamespace(name="西湖", address=None, lat=24.4400, lon=118.4200)
    assert judge(short, [g("A", "西湖水鳥保護區", 24.4401, 118.42)])[0] is None


def test_same_name_rules_take_precedence_over_contained():
    res = [g("A", "太平山國家森林遊樂區", 24.5620, 121.4995), g("B", "太平山國家森林遊樂區停車場", 24.5576, 121.4995)]
    assert judge(PLACE, res) == ("A", ["A", "B"], "自動接受：同名且 1 km 內唯一")


def test_sub_area_rule_accepts_parent_only_when_close_and_unique():
    garden = SimpleNamespace(
        name="國立自然科學博物館之植物園", address="臺中市北區館前路1號", lat=24.15812, lon=120.66817
    )
    res = [g("A", "國立自然科學博物館", 24.15815, 120.66820, "404臺中市北區館前路1號")]
    assert judge(garden, res) == ("A", ["A"], "自動接受：來源名稱包含 Google 名稱且門牌相同，且只有一筆")
    far = [g("A", "國立自然科學博物館", 24.17, 120.67, "404臺中市北區另一路2號")]
    assert judge(garden, far) == (None, ["A"], "來源名稱包含 Google 名稱但距離 >100 m，且門牌不同")
    two = [g("A", "自然科學博物館", 24.15815, 120.6682), g("B", "科學博物館之植物", 24.15813, 120.6682)]
    assert judge(garden, two)[2] == "多個來源名稱包含 Google 名稱的候選（2 筆）符合門牌或距離"


def test_sub_area_parent_already_in_db_stays_pending(monkeypatch):
    import asyncio

    from scripts import place_ids as m

    calls = []

    async def fake_accept(factory, place_id, gpid, reason, *, mark_conflict=True):
        calls.append(mark_conflict)
        return "mapping_conflict"

    monkeypatch.setattr(m, "_accept", fake_accept)
    rule = "自動接受：來源名稱包含 Google 名稱且門牌相同，且只有一筆"
    assert asyncio.run(m._settle(None, None, "A", rule, "recheck")) == ("review", m.SUB_AREA_TAKEN)
    assert asyncio.run(m._settle(None, None, "A", "自動接受：同名且 100 m 內唯一", "recheck")) == (
        "conflict",
        m.CONFLICT_REASON,
    )
    assert calls == [False, True]


def test_admin_prefix_and_parenthesised_alias_count_as_same_name():
    p = SimpleNamespace(name="新竹市玻璃工藝博物館", address=None, lat=24.8, lon=120.97)
    assert judge(p, [g("A", "玻璃工藝博物館", 24.8005, 120.97)])[0] == "A"
    lib = SimpleNamespace(name="龍岡圖書館(桃園市立圖書館龍岡分館)", address=None, lat=24.95, lon=121.22)
    assert judge(lib, [g("A", "龍岡圖書館", 24.9505, 121.22)])[0] == "A"
    assert judge(lib, [g("A", "桃園市立圖書館龍岡分館", 24.9505, 121.22)])[0] == "A"


def test_recheck_selection():
    from scripts.place_ids import _selected

    assert _selected("某公園", "名稱不同（Google 前 1 筆皆不同名）", None, False)
    assert _selected("某公園", "來源名稱包含 Google 名稱，可能是子區域對到母場館", ["來源名稱包含"], False)
    assert not _selected("某公園", "名稱不同（Google 前 1 筆皆不同名）", ["來源名稱包含"], False)
    assert _selected("國立臺灣博物館", "名稱不同（Google 前 1 筆皆不同名）", ["來源名稱包含"], True)
    assert _selected("台南：某觀光工廠", "x", None, True) and _selected("某館(別名)", "x", None, True)
    assert not _selected("某公園", "x", None, True)


def test_plan_dedupe():
    import uuid

    from scripts.place_ids import DedupPlace, plan_dedupe

    def place(name, lat, *members):
        return DedupPlace(uuid.uuid4(), name, lat, 121.5, tuple(members))

    a = place("新竹市玻璃工藝博物館", 25.0, ("ds1", "a1", "新竹市玻璃工藝博物館", ""), ("ds2", "a2", "玻璃館", ""))
    b = place("玻璃工藝博物館", 25.003, ("ds3", "b1", "玻璃工藝博物館", "新竹市東大路"))
    far = place("玻璃工藝博物館", 25.02, ("ds3", "b2", "玻璃工藝博物館", ""))
    other = place("某公園", 25.0, ("ds3", "b3", "某公園", ""))
    rows, manual = plan_dedupe([(a, b), (a, far), (a, other)], "2026-10-27")
    assert [(r[0], r[1], r[4], r[5], r[10]) for r in rows] == [
        ("ds1", "a1", "ds3", "b1", "accept"),
        ("ds2", "a2", "ds3", "b1", "accept"),
    ]
    assert [(x[1].members[0][1], round(x[2] / 100)) for x in manual] == [("b2", 22), ("b3", 0)]


def test_recheck_keeps_conflict_rows_without_new_search():
    from scripts.place_ids import CONFLICT_REASON, REVIEW_HEADER, _kept_row

    p = SimpleNamespace(id="01a15a1a-0000-7000-8000-000000000001", name="某公園", address=None, lat=25.0, lon=121.5)
    old = dict.fromkeys(REVIEW_HEADER, "")
    old.update(place_id=p.id, name="某公園", candidate_place_ids="ChIJx", reason=CONFLICT_REASON, decision="reject")
    kept = dict(zip(REVIEW_HEADER, _kept_row(p, old, CONFLICT_REASON), strict=True))
    assert kept["candidate_place_ids"] == "ChIJx" and kept["decision"] == "reject"
    fresh = dict(zip(REVIEW_HEADER, _kept_row(p, None, CONFLICT_REASON), strict=True))
    assert fresh["reason"] == CONFLICT_REASON and fresh["status"] == "pending" and fresh["decision"] == ""
