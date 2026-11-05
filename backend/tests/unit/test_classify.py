"""景點細分類型：來源分類（confirmed）、名稱推定（inferred）、各處類型清單一致。"""

from __future__ import annotations

from typing import get_args

from app.domain.schemas import MAX_DEFAULT_STAY, TYPE_DEFAULT_STAY, TypePref
from etl.classify import category_types, name_types
from etl.model import PLACE_TYPES, PRIMARY_TYPE_PRIORITY, TYPE_INDOOR, SourceRec
from etl.resolve import Cluster, merge
from scripts.place_ids import PRIMARY_TYPES


def rec(name, ds="tdx_attractions", classes=None, cats=None):
    display = {}
    if classes:
        display["attraction_classes"] = classes
    if cats:
        display["categories"] = cats
    return SourceRec(ds, "k", name, "attraction", city="臺北市", lat=25.0, lon=121.5, display=display)


def test_type_lists_consistent_everywhere():
    assert set(PRIMARY_TYPE_PRIORITY) == set(PLACE_TYPES) == set(get_args(TypePref)) == set(TYPE_DEFAULT_STAY)
    assert tuple(PRIMARY_TYPES) == PRIMARY_TYPE_PRIORITY and PRIMARY_TYPE_PRIORITY[-1] == "other"
    assert set(TYPE_INDOOR) <= set(PLACE_TYPES)
    assert all(v % 15 == 0 and 15 <= v <= MAX_DEFAULT_STAY for v in TYPE_DEFAULT_STAY.values())


def test_name_rules():
    def ts(n):
        return set(name_types(n))

    assert {"temple"} <= ts("鄞山寺") and {"old_street"} <= ts("九份老街")
    assert "night_market" in ts("羅東觀光夜市") and "trail" in ts("茶亭古道")
    assert "beach" in ts("福隆海水浴場") and "zoo" in ts("新竹市立動物園")
    assert "heritage" in ts("北門承恩門") and "library" in ts("國立臺灣圖書館")
    assert "waterfront" not in ts("小台灣")
    assert "heritage" not in ts("老鷹溪瀑布") and "old_street" not in ts("老街溪水岸自行車道")
    assert "amusement_park" not in ts("太平山國家森林遊樂區")
    assert "park_playground" not in ts("陽明山國家公園")
    assert "campus" not in ts("餅乾學院School of cookie")
    assert ts("某某某") == set()
    assert name_types("鄞山寺")["temple"].confirmation == "inferred"


def test_category_types_confirmed_and_park_needs_park_name():
    t = category_types(rec("臺北賓館", classes=["公園綠地類", "文化資產類", "藝文場館類"]))
    assert set(t) == {"heritage", "arts_venue"} and t["heritage"].confirmation == "confirmed"
    assert "park_playground" not in category_types(rec("某園區", "tainan_attractions", cats=["公園綠地"]))
    assert "park_playground" in category_types(rec("巴克禮紀念公園", "tainan_attractions", cats=["公園綠地"]))
    assert category_types(rec("某處", classes=["文化類", "遊憩類"])) == {}


def test_merge_primary_type_and_indoor_follow_priority():
    m = merge(Cluster("attraction", [rec("臺北市立動物園", classes=["生態場館類"])]))
    assert m is not None and m.primary_type == "zoo" and m.indoor is not None
    assert (m.indoor.value, m.indoor.confirmation) == ("outdoor", "inferred")
    q = merge(Cluster("attraction", [rec("澎湖水族館")]))
    assert q is not None and q.primary_type == "aquarium" and q.indoor is not None and q.indoor.value == "indoor"
    t = merge(Cluster("attraction", [rec("龍山寺", classes=["宗教廟宇類", "文化資產類"])]))
    assert t is not None and t.primary_type == "temple" and t.indoor is not None and t.indoor.value == "outdoor"
    o = merge(Cluster("attraction", [rec("某某某")]))
    assert o is not None and o.primary_type == "other" and o.indoor is None
