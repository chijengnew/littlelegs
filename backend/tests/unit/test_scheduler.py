"""排序與可行性。固定輸入、固定時間；不呼叫外部服務。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.domain.hours import OpeningInfo
from app.domain.scheduler import Leg, Problem, StopSpec, solve
from app.timeutil import local_dt

D = date(2026, 10, 22)
A = "019a0000-0000-7000-8000-00000000000a"
B = "019a0000-0000-7000-8000-00000000000b"
C = "019a0000-0000-7000-8000-00000000000c"


def t(h, m=0) -> datetime:
    return local_dt(D, time(h, m))


def open_(h0, h1, status="known") -> OpeningInfo:
    return OpeningInfo(status, [(t(h0), t(h1))] if h1 is not None else [])


def legs(n: int, secs: int = 1200, **over) -> dict:
    out = {(i, j): Leg("ok", 0 if i == j else secs, 0) for i in range(n) for j in range(n)}
    for k, v in over.items():
        i, j = (int(x) for x in k[1:].split("_"))
        out[(i, j)] = v
    return out


def stop(ref, loc, stay=60, opening=None, src="type_default", **kw) -> StopSpec:
    return StopSpec(ref, loc, stay, src, opening or open_(8, 20), **kw)


def prob(stops, lg, depart=(9, 0), ret=(18, 0), nap=None, meals=()):
    return Problem(t(*depart), t(*ret), 0, 0, stops, lg, nap, list(meals))


def kinds(sol):
    return [(i.type, i.start.strftime("%H:%M"), i.end.strftime("%H:%M"), i.reason) for i in sol.items]


def test_single_stop_includes_both_legs_without_buffer():
    sol = solve(prob([stop(A, 1, src="user")], legs(2, 1800)), "auto")
    assert sol.feasibility == "feasible"
    ks = kinds(sol)
    assert ks[0][:3] == ("move", "09:00", "09:30")
    assert ks[1][:3] == ("attraction", "09:30", "10:30")
    assert ks[-1][:3] == ("move", "10:30", "11:00")
    assert not any(i.type == "rest" for i in sol.items)


def test_stay_estimated_is_informational_only():
    sol = solve(prob([stop(A, 1)], legs(2)), "auto")
    assert sol.feasibility == "feasible" and "stay_estimated" in sol.warnings


def test_exact_fit_and_one_minute_over():
    fit = solve(prob([stop(A, 1, stay=360, src="user")], legs(2, 1800), ret=(16, 0)), "auto")
    assert fit.feasibility == "feasible"
    over = solve(prob([stop(A, 1, stay=360, src="user")], legs(2, 1801), ret=(16, 0)), "auto")
    assert over.feasibility == "infeasible" and "RETURN_TIME_EXCEEDED" in over.violation_codes


def test_travel_seconds_not_rounded_down():
    sol = solve(prob([stop(A, 1, src="user")], legs(2, 1201)), "auto")
    move = next(i for i in sol.items if i.type == "move")
    att = next(i for i in sol.items if i.type == "attraction")
    assert move.end == t(9, 21) and move.travel_seconds == 1201
    assert att.start == t(9, 21)


def test_timeline_has_no_unlisted_gap():
    sol = solve(
        prob(
            [stop(A, 1, opening=open_(10, 17), src="user"), stop(B, 2, src="user")],
            legs(3, 1201),
            ret=(20, 0),
            nap=(t(13), t(14)),
            meals=[("lunch", t(11, 30), t(13))],
        ),
        "auto",
    )
    assert sol.feasibility == "feasible"
    assert sol.items[0].start == t(9)
    assert all(a.end == b.start for a, b in zip(sol.items, sol.items[1:], strict=False))


def test_real_wait_is_listed_from_arrival():
    sol = solve(prob([stop(A, 1, opening=open_(10, 17), src="user")], legs(2, 1201)), "auto")
    rest = [i for i in sol.items if i.type == "rest"]
    assert len(rest) == 1 and rest[0].reason == "wait" and not rest[0].estimated
    assert (rest[0].start, rest[0].end) == (t(9, 21), t(10))


def test_ranking_compares_actual_travel_seconds():
    lg = legs(3, 602)
    lg[(0, 2)] = Leg("ok", 601, 0)
    lg[(2, 1)] = Leg("ok", 601, 0)
    lg[(1, 0)] = Leg("ok", 601, 0)
    sol = solve(prob([stop(A, 1, src="user"), stop(B, 2, src="user")], lg), "auto")
    assert sol.order == [B, A]


def test_arrive_before_opening_waits():
    sol = solve(prob([stop(A, 1, opening=open_(11, 17), src="user")], legs(2)), "auto")
    att = next(i for i in sol.items if i.type == "attraction")
    assert att.start == t(11)
    assert any(i.type == "rest" and i.reason == "wait" for i in sol.items)


def test_stay_crossing_closing_is_infeasible():
    sol = solve(prob([stop(A, 1, stay=120, opening=open_(9, 11), src="user")], legs(2)), "auto")
    assert sol.feasibility == "infeasible" and "OPENING_HOURS" in sol.violation_codes


def test_nap_continuous_and_covered_by_move_and_rest():
    nap = (t(12), t(14))
    sol = solve(
        prob([stop(A, 1, stay=150, src="user"), stop(B, 2, stay=60, src="user")], legs(3, 1800), nap=nap), "auto"
    )
    assert sol.feasibility == "feasible"
    for i in sol.items:
        if i.type in ("attraction", "meal"):
            assert i.end <= nap[0] or i.start >= nap[1]
    covered = sorted(
        (max(i.start, nap[0]), min(i.end, nap[1]))
        for i in sol.items
        if i.type in ("move", "rest") and i.end > nap[0] and i.start < nap[1]
    )
    cur = nap[0]
    for a, b in covered:
        assert a <= cur
        cur = max(cur, b)
    assert cur >= nap[1]


def test_meal_60_minutes_inside_window_not_overlapping():
    sol = solve(
        prob(
            [stop(A, 1, stay=120, src="user"), stop(B, 2, stay=120, src="user")],
            legs(3),
            meals=[("lunch", t(11, 30), t(13, 30))],
        ),
        "auto",
    )
    meal = [i for i in sol.items if i.type == "meal"]
    assert len(meal) == 1 and meal[0].end - meal[0].start == timedelta(minutes=60)
    assert t(11, 30) <= meal[0].start and meal[0].end <= t(13, 30)
    others = [i for i in sol.items if i.type in ("attraction", "move")]
    assert all(o.end <= meal[0].start or o.start >= meal[0].end for o in others)


def test_overlapping_meal_windows_still_schedulable():
    sol = solve(
        prob([stop(A, 1, src="user")], legs(2), ret=(20, 0), meals=[("lunch", t(12), t(14)), ("dinner", t(13), t(15))]),
        "auto",
    )
    meals = sorted((i for i in sol.items if i.type == "meal"), key=lambda i: i.start)
    assert len(meals) == 2 and meals[0].end <= meals[1].start


def test_meal_window_swallowed_by_nap_is_input_conflict_without_removal_suggestion():
    sol = solve(prob([stop(A, 1)], legs(2), nap=(t(12), t(13, 30)), meals=[("lunch", t(12), t(14))]), "auto")
    assert sol.feasibility == "infeasible" and "MEAL_NAP_CONFLICT" in sol.violation_codes
    assert sol.suggest_remove == []


def test_unknown_travel_is_unverified_without_timeline():
    lg = legs(2)
    lg[(0, 1)] = Leg("unknown")
    sol = solve(prob([stop(A, 1)], lg), "manual")
    assert sol.feasibility == "unverified" and sol.items == [] and "travel_unavailable" in sol.warnings


def test_route_not_found_is_infeasible():
    lg = legs(2)
    lg[(0, 1)] = Leg("no_route")
    sol = solve(prob([stop(A, 1)], lg), "auto")
    assert sol.feasibility == "infeasible" and sol.violation_codes == ["ROUTE_NOT_FOUND"]


def test_provisional_hours_no_solution_is_unverified_not_infeasible():
    sol = solve(prob([stop(A, 1, stay=120, opening=open_(9, 10, "provisional"))], legs(2)), "auto")
    assert sol.feasibility == "unverified"
    assert "special_hours_unverified" in sol.warnings


def test_hours_unknown_allowed_but_unverified():
    sol = solve(prob([stop(A, 1, opening=OpeningInfo("unknown"), src="user")], legs(2)), "auto")
    assert sol.feasibility == "unverified" and "hours_unknown" in sol.warnings and sol.items


def test_provisional_hours_that_fit_are_feasible_with_reminder():
    sol = solve(prob([stop(A, 1, opening=open_(9, 18, "provisional"), src="user")], legs(2)), "auto")
    assert sol.feasibility == "feasible" and "special_hours_unverified" in sol.warnings


def test_hard_violation_infeasible_and_suggested():
    sol = solve(prob([stop(A, 1, violations={"INDOOR_REQUIRED"}), stop(B, 2)], legs(3)), "auto")
    assert sol.feasibility == "infeasible" and A in sol.suggest_remove


def test_manual_keeps_user_order_auto_picks_shorter():
    lg = legs(3, 600)
    lg[(1, 2)] = Leg("ok", 5400, 0)
    lg[(2, 1)] = Leg("ok", 600, 0)
    stops = [stop(A, 1, src="user"), stop(B, 2, src="user")]
    manual = solve(prob(stops, lg), "manual")
    auto = solve(prob(stops, lg), "auto")
    assert manual.order == [A, B]
    assert auto.order == [B, A] and auto.optimal_claimed


def test_tie_break_by_internal_id_bytes():
    stops = [stop(B, 2, src="user"), stop(A, 1, src="user")]
    sol = solve(prob(stops, legs(3)), "auto")
    assert sol.order == [A, B]


def test_timeout_reports_search_incomplete_not_infeasible():
    stops = [stop(r, i + 1, stay=15, src="user") for i, r in enumerate([A, B, C, A[:-1] + "d", A[:-1] + "e"])]
    sol = solve(prob(stops, legs(6, 300), ret=(23, 0)), "auto", budget_s=0.0)
    assert sol.feasibility == "unverified" and "search_incomplete" in sol.warnings
    assert not sol.optimal_claimed


def test_remove_one_suggestion_uses_existing_matrix():
    stops = [stop(A, 1, stay=180, src="user"), stop(B, 2, stay=180, src="user"), stop(C, 3, stay=180, src="user")]
    sol = solve(prob(stops, legs(4, 900), ret=(17, 0)), "auto")
    assert sol.feasibility == "infeasible"
    assert set(sol.suggest_remove) == {A, B, C}


def test_same_place_as_endpoint_and_stop():
    sol = solve(Problem(t(9), t(18), 0, 0, [stop(A, 0, src="user")], {}, None, []), "auto")
    assert sol.feasibility == "feasible"
    assert [i.type for i in sol.items if i.type != "rest"] == ["attraction"]
