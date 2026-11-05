"""Place ID 匯出／匯入：以來源紀錄鍵對應地點，衝突一律略過不覆寫。"""

from __future__ import annotations

import uuid

import pytest

from scripts.place_ids import EXPORT_HEADER, ImportTarget, _read_export, plan_import

A, B = uuid.uuid4(), uuid.uuid4()


def t(pid, status="none", gpid=None):
    return ImportTarget(pid, status, gpid)


def test_single_place_accepted_even_if_some_keys_missing():
    todo, out = plan_import({"G1": {("ds", "1"), ("ds", "gone")}}, {("ds", "1"): t(A)}, {})
    assert out == {"G1": "accepted"}
    assert todo == [("G1", t(A))]


def test_keys_split_across_places_skipped():
    todo, out = plan_import({"G1": {("ds", "1"), ("ds", "2")}}, {("ds", "1"): t(A), ("ds", "2"): t(B)}, {})
    assert todo == [] and out["G1"] == "來源紀錄對到多個地點"


def test_no_matching_key_skipped():
    todo, out = plan_import({"G1": {("ds", "x")}}, {("ds", "1"): t(A)}, {})
    assert todo == [] and out["G1"] == "找不到對應的來源紀錄"


def test_two_ids_for_same_place_both_skipped():
    todo, out = plan_import({"G1": {("ds", "1")}, "G2": {("ds2", "9")}}, {("ds", "1"): t(A), ("ds2", "9"): t(A)}, {})
    assert todo == []
    assert out == {"G1": "多個 Place ID 對到同一地點", "G2": "多個 Place ID 對到同一地點"}


def test_existing_state_is_never_overwritten():
    groups = {"G1": {("ds", "1")}, "G2": {("ds", "2")}, "G3": {("ds", "3")}, "G4": {("ds", "4")}}
    c, d = uuid.uuid4(), uuid.uuid4()
    targets = {
        ("ds", "1"): t(A, "accepted", "G1"),
        ("ds", "2"): t(B, "accepted", "Gx"),
        ("ds", "3"): t(c, "no_match"),
        ("ds", "4"): t(d),
    }
    todo, out = plan_import(groups, targets, {"G1": A, "Gx": B, "G4": uuid.uuid4()})
    assert todo == []
    assert out == {
        "G1": "unchanged",
        "G2": "地點已有其他 Place ID",
        "G3": "地點狀態為 no_match，不覆寫",
        "G4": "Place ID 已被其他地點使用",
    }


def test_alias_of_same_place_allowed():
    todo, out = plan_import({"G1": {("ds", "1")}}, {("ds", "1"): t(A)}, {"G1": A})
    assert out == {"G1": "accepted"} and len(todo) == 1


def test_read_export_groups_rows(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text(
        ",".join(EXPORT_HEADER)
        + "\nG1,ds,1,2026-10-22T13:40:00+00:00,甲\nG1,ds2,a|b,2026-10-22T13:40:00+00:00,甲\nG2,ds,2,,乙\n",
        encoding="utf-8-sig",
    )
    groups, checked, names = _read_export(str(p))
    assert groups == {"G1": {("ds", "1"), ("ds2", "a|b")}, "G2": {("ds", "2")}}
    assert checked["G1"] is not None and checked["G1"].utcoffset() is not None
    assert checked["G2"] is None and names == {"G1": "甲", "G2": "乙"}


def test_read_export_rejects_wrong_header(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("place_id,name\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        _read_export(str(p))
