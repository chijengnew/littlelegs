"""行程排序與可行性。純函式、無 I/O，可用固定輸入以 pytest 測試。

離散模型：
- 項目：attraction／meal／rest／move。抵達時間往上取到整分鐘（車程不向下取整），景點與用餐從抵達當下開始，
  時間軸沒有未列出的空檔；等開門、等用餐時段與午睡一律列為 rest。
- 不預留抵達緩衝或休息（2026-11-05 決定）：需要多留時間由使用者拉長停留時間。
- 午睡 [start, end) 內不得有景點或用餐，可由移動與休息共同覆蓋。
- 用餐固定連續 60 分鐘、位於使用者時窗內、不與午睡／景點／移動重疊；在當下所在位置進行（不指定餐廳）。
- 已知營業時間必須覆蓋整段停留。

搜尋：對每種景點排列（≤5! = 120）做有限狀態動態規劃，狀態＝(已完成景點數, 位置階段, 已完成用餐)，
保留各狀態最早時間（可自由等待，故較早時間支配較晚時間）；用餐可插在任一位置，不是只用最早抵達的貪婪安排。
搜尋空間是上述 MVP 離散模型，不宣稱是所有現實安排的全域最佳解。
"""

from __future__ import annotations

import itertools
import time as _time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.domain.hours import OpeningInfo
from app.timeutil import ceil_minute

MEAL = timedelta(minutes=60)

UNVERIFIED_WARNINGS = {
    "hours_unknown",
    "weather_unverified",
    "indoor_inferred",
    "travel_unavailable",
    "search_incomplete",
    "place_removed",
}
INFO_WARNINGS = {"stay_estimated", "special_hours_unverified"}


@dataclass(frozen=True)
class Leg:
    status: str
    seconds: int | None = None
    meters: int | None = None


@dataclass
class StopSpec:
    ref: str
    loc: int
    stay_minutes: int
    stay_source: str
    opening: OpeningInfo
    warnings: set[str] = field(default_factory=set)
    violations: set[str] = field(default_factory=set)


@dataclass
class Problem:
    depart: datetime
    ret: datetime
    start_loc: int
    end_loc: int
    stops: list[StopSpec]
    legs: dict[tuple[int, int], Leg]
    nap: tuple[datetime, datetime] | None = None
    meals: list[tuple[str, datetime, datetime]] = field(default_factory=list)
    global_warnings: set[str] = field(default_factory=set)


@dataclass
class Item:
    type: str
    start: datetime
    end: datetime
    place_ref: str | None = None
    from_loc: int | None = None
    to_loc: int | None = None
    meal: str | None = None
    reason: str | None = None
    estimated: bool = False
    source: str = "system"
    distance_m: int | None = None
    travel_seconds: int | None = None


@dataclass
class PermResult:
    order: tuple[int, ...]
    status: str
    items: list[Item] = field(default_factory=list)
    move_seconds: int = 0
    arrival_end: datetime | None = None
    warnings: set[str] = field(default_factory=set)


@dataclass
class Solution:
    feasibility: str
    order: list[str]
    items: list[Item]
    warnings: set[str]
    violation_codes: list[str]
    violation_details: list[dict]
    suggest_remove: list[str]
    search_complete: bool
    optimal_claimed: bool
    perms_evaluated: int


class _Deadline:
    def __init__(self, seconds: float) -> None:
        self.t = _time.monotonic() + seconds

    def expired(self) -> bool:
        return _time.monotonic() >= self.t


def _push_past_nap(s: datetime, dur: timedelta, nap: tuple[datetime, datetime] | None) -> datetime:
    if nap and s < nap[1] and s + dur > nap[0]:
        return ceil_minute(nap[1])
    return s


def _earliest_visit(t_ready: datetime, stop: StopSpec, nap, relax_hours: bool) -> datetime | None:
    dur = timedelta(minutes=stop.stay_minutes)
    s0 = ceil_minute(t_ready)
    if relax_hours or not stop.opening.usable:
        return _push_past_nap(s0, dur, nap)
    for o, c in stop.opening.intervals:
        s = ceil_minute(max(s0, o))
        s = _push_past_nap(s, dur, nap)
        if s >= o and s + dur <= c:
            return s
    return None


def _earliest_meal(t_ready: datetime, ws: datetime, we: datetime, nap) -> datetime | None:
    s = ceil_minute(max(t_ready, ws))
    s = _push_past_nap(s, MEAL, nap)
    return s if s + MEAL <= we else None


@dataclass
class _Relax:
    hours: frozenset[int] = frozenset()
    all_hours: bool = False
    meals: bool = False
    nap: bool = False
    ret: bool = False


def _solve_perm(p: Problem, order: tuple[int, ...], relax: _Relax = _Relax()) -> PermResult:
    n = len(order)
    meals = [] if relax.meals else p.meals
    nap = None if relax.nap else p.nap
    full = (1 << len(meals)) - 1
    best: dict[tuple, tuple[datetime, tuple | None, tuple | None]] = {}

    def relax_state(key, t, prev, action):
        cur = best.get(key)
        if cur is None or t < cur[0]:
            best[key] = (t, prev, action)

    def loc_of(k: int, phase: int) -> int:
        if phase == 2:
            return p.end_loc
        if phase == 1:
            return p.stops[order[k]].loc
        return p.start_loc if k == 0 else p.stops[order[k - 1]].loc

    relax_state((0, 0, 0), p.depart, None, None)
    travel_unknown = False
    no_route = False
    masks = sorted(range(full + 1), key=lambda m: bin(m).count("1"))

    for k in range(n + 1):
        for mask in masks:
            key = (k, 0, mask)
            if key not in best:
                continue
            t = best[key][0]
            here = loc_of(k, 0)
            for i, (_meal, ws, we) in enumerate(meals):
                if mask >> i & 1:
                    continue
                s = _earliest_meal(t, ws, we, nap)
                if s is not None:
                    relax_state((k, 0, mask | 1 << i), s + MEAL, key, ("meal", i, s, here))
            dest = p.end_loc if k == n else p.stops[order[k]].loc
            leg = p.legs.get((here, dest)) if here != dest else Leg("ok", 0, 0)
            if leg is None or leg.status == "unknown":
                travel_unknown = True
                continue
            if leg.status == "no_route":
                no_route = True
                continue
            secs = 0 if here == dest else leg.seconds or 0
            a = ceil_minute(t + timedelta(seconds=secs))
            relax_state((n, 2, mask) if k == n else (k, 1, mask), a, key, ("move", here, dest, t, a, leg.meters, secs))
        if k == n:
            break
        stop_i = order[k]
        stop = p.stops[stop_i]
        relax_hours = relax.all_hours or stop_i in relax.hours
        for mask in masks:
            key = (k, 1, mask)
            if key not in best:
                continue
            t = best[key][0]
            for i, (_meal, ws, we) in enumerate(meals):
                if mask >> i & 1:
                    continue
                s = _earliest_meal(t, ws, we, nap)
                if s is not None:
                    relax_state((k, 1, mask | 1 << i), s + MEAL, key, ("meal", i, s, stop.loc))
            s = _earliest_visit(t, stop, nap, relax_hours)
            if s is not None:
                relax_state((k + 1, 0, mask), s + timedelta(minutes=stop.stay_minutes), key, ("visit", stop_i, s))
    for mask in masks:
        key = (n, 2, mask)
        if key not in best:
            continue
        t = best[key][0]
        for i, (_meal, ws, we) in enumerate(meals):
            if mask >> i & 1:
                continue
            s = _earliest_meal(t, ws, we, nap)
            if s is not None:
                relax_state((n, 2, mask | 1 << i), s + MEAL, key, ("meal", i, s, p.end_loc))

    final_key = (n, 2, full)
    if final_key not in best or (not relax.ret and best[final_key][0] > p.ret):
        status = "travel_unknown" if travel_unknown else ("no_route" if no_route else "no_solution")
        return PermResult(order, status)

    actions = []
    cur: tuple | None = final_key
    while cur is not None:
        _t, prev, action = best[cur]
        if action is not None:
            actions.append(action)
        cur = prev
    actions.reverse()
    items, move_s, arrival_end = _timeline(p, actions, meals, nap)
    return PermResult(order, "ok", items, move_s, arrival_end)


def _timeline(p: Problem, actions: list[tuple], meals, nap) -> tuple[list[Item], int, datetime | None]:
    items: list[Item] = []
    t = p.depart
    move_s = 0
    arrival_end = None

    def add_rest(until: datetime) -> None:
        nonlocal t
        if until <= t:
            return
        if nap is not None and t < nap[1] and until > nap[0]:
            if t < nap[0]:
                items.append(Item("rest", t, nap[0], reason="wait"))
            items.append(Item("rest", max(t, nap[0]), min(until, nap[1]), reason="nap"))
            if until > nap[1]:
                items.append(Item("rest", nap[1], until, reason="wait"))
        else:
            items.append(Item("rest", t, until, reason="wait"))
        t = until

    for act in actions:
        kind = act[0]
        if kind == "move":
            _, here, dest, m, a, meters, secs = act
            if here != dest:
                items.append(
                    Item(
                        "move",
                        m,
                        a,
                        from_loc=here,
                        to_loc=dest,
                        estimated=True,
                        source="google",
                        distance_m=meters,
                        travel_seconds=secs,
                    )
                )
                move_s += secs
            t = a
            arrival_end = a
        elif kind == "meal":
            _, i, s, loc = act
            add_rest(s)
            items.append(Item("meal", s, s + MEAL, meal=meals[i][0], to_loc=loc))
            t = s + MEAL
        elif kind == "visit":
            _, stop_i, s = act
            stop = p.stops[stop_i]
            add_rest(s)
            items.append(
                Item(
                    "attraction",
                    s,
                    s + timedelta(minutes=stop.stay_minutes),
                    place_ref=stop.ref,
                    to_loc=stop.loc,
                    estimated=stop.stay_source != "user",
                )
            )
            t = s + timedelta(minutes=stop.stay_minutes)
    return items, move_s, arrival_end


def _id_bytes(ref: str) -> bytes:
    return uuid.UUID(ref).bytes


def _stop_warnings(p: Problem, order: tuple[int, ...]) -> set[str]:
    w = set(p.global_warnings)
    for i in order:
        st = p.stops[i]
        w |= st.warnings
        if st.opening.status == "unknown":
            w.add("hours_unknown")
        elif st.opening.status == "provisional":
            w.add("special_hours_unverified")
        if st.stay_source != "user":
            w.add("stay_estimated")
    return w


def _diagnose(p: Problem, order: tuple[int, ...]) -> tuple[list[str], list[dict]]:
    codes: list[str] = []
    details: list[dict] = []
    if _solve_perm(p, order, _Relax(ret=True)).status == "ok":
        codes.append("RETURN_TIME_EXCEEDED")
        details.append({"code": "RETURN_TIME_EXCEEDED", "until": p.ret.isoformat()})
    if _solve_perm(p, order, _Relax(all_hours=True)).status == "ok":
        codes.append("OPENING_HOURS")
        for i in order:
            if _solve_perm(p, order, _Relax(hours=frozenset({i}))).status == "ok":
                st = p.stops[i]
                details.append(
                    {
                        "code": "OPENING_HOURS",
                        "place_ref": st.ref,
                        "intervals": [[a.isoformat(), b.isoformat()] for a, b in st.opening.intervals],
                    }
                )
    if p.meals and _solve_perm(p, order, _Relax(meals=True)).status == "ok":
        codes.append("MEAL_UNSCHEDULABLE")
        details.append(
            {"code": "MEAL_UNSCHEDULABLE", "windows": [[m, a.isoformat(), b.isoformat()] for m, a, b in p.meals]}
        )
    if p.nap and _solve_perm(p, order, _Relax(nap=True)).status == "ok":
        codes.append("NAP_CONFLICT")
        details.append({"code": "NAP_CONFLICT", "nap": [p.nap[0].isoformat(), p.nap[1].isoformat()]})
    if not codes:
        options: list[tuple[str, dict[str, Any]]] = [
            ("RETURN_TIME_EXCEEDED", {"ret": True}),
            ("OPENING_HOURS", {"all_hours": True}),
        ]
        if p.meals:
            options.append(("MEAL_UNSCHEDULABLE", {"meals": True}))
        if p.nap:
            options.append(("NAP_CONFLICT", {"nap": True}))
        for (c1, r1), (c2, r2) in itertools.combinations(options, 2):
            if _solve_perm(p, order, _Relax(**r1, **r2)).status == "ok":
                for c in (c1, c2):
                    if c not in codes:
                        codes.append(c)
                        details.append({"code": c, "combined": True})
    if not codes:
        codes.append("TIME_WINDOW_INSUFFICIENT")
        details.append({"code": "TIME_WINDOW_INSUFFICIENT"})
    return codes, details


def input_conflicts(p: Problem) -> list[dict]:
    """純條件衝突（與景點無關）：用餐時窗扣掉午睡後放不下 60 分鐘、兩餐無法互不重疊。"""
    out = []
    for name, ws, we in p.meals:
        if _earliest_meal(ws, ws, we, p.nap) is None:
            out.append({"code": "MEAL_NAP_CONFLICT", "meal": name})
    if len(p.meals) == 2:
        (_, a0, a1), (_, b0, b1) = p.meals
        sa = _earliest_meal(a0, a0, a1, p.nap)
        ok = False
        if sa is not None:
            ok = _earliest_meal(sa + MEAL, b0, b1, p.nap) is not None
        sb = _earliest_meal(b0, b0, b1, p.nap)
        if not ok and sb is not None:
            ok = _earliest_meal(sb + MEAL, a0, a1, p.nap) is not None
        if not ok and not out:
            out.append({"code": "MEALS_OVERLAP", "meal": "lunch+dinner"})
    return out


def solve(p: Problem, mode: str, budget_s: float = 5.0) -> Solution:
    """mode='auto'：枚舉排列挑最佳；mode='manual'：只檢查給定順序（stops 原順序），不偷偷排序。"""
    dl = _Deadline(budget_s)
    n = len(p.stops)
    hard: set[str] = set()
    hard_details: list[dict] = []
    for st in p.stops:
        for v in st.violations:
            hard.add(v)
            hard_details.append({"code": v, "place_ref": st.ref})
        if st.opening.status in ("closed_permanently", "closed_temporarily"):
            hard.add("PLACE_CLOSED")
            hard_details.append({"code": "PLACE_CLOSED", "place_ref": st.ref, "status": st.opening.status})
    conflicts = input_conflicts(p)

    perms = list(itertools.permutations(range(n))) if mode == "auto" else [tuple(range(n))]
    results: list[PermResult] = []
    complete = True
    for perm in perms:
        if dl.expired():
            complete = False
            break
        r = _solve_perm(p, perm)
        r.warnings = _stop_warnings(p, perm)
        results.append(r)

    ok = [r for r in results if r.status == "ok"]

    def rank(r: PermResult):
        unver = len(r.warnings & UNVERIFIED_WARNINGS)
        return (
            unver,
            r.move_seconds,
            r.arrival_end or r.items[-1].end,
            tuple(_id_bytes(p.stops[i].ref) for i in r.order),
        )

    if ok and not hard and not conflicts:
        bestr = min(ok, key=rank)
        w = set(bestr.warnings)
        if not complete:
            w.add("search_incomplete")
        feas = "unverified" if w & UNVERIFIED_WARNINGS else "feasible"
        all_evaluable = not any(r.status == "travel_unknown" for r in results)
        return Solution(
            feas,
            [p.stops[i].ref for i in bestr.order],
            bestr.items,
            w,
            [],
            [],
            [],
            complete,
            complete and all_evaluable and mode == "auto",
            len(results),
        )

    base_w = _stop_warnings(p, tuple(range(n)))
    order_refs = [p.stops[i].ref for i in (results[0].order if results else range(n))]
    if hard or conflicts:
        codes = sorted(hard | {c["code"] for c in conflicts})
        sugg = sorted({d["place_ref"] for d in hard_details if "place_ref" in d})
        return Solution(
            "infeasible", order_refs, [], base_w, codes, hard_details + conflicts, sugg, complete, False, len(results)
        )
    if not complete:
        return Solution(
            "unverified", order_refs, [], base_w | {"search_incomplete"}, [], [], [], False, False, len(results)
        )
    if any(r.status == "travel_unknown" for r in results):
        return Solution(
            "unverified", order_refs, [], base_w | {"travel_unavailable"}, [], [], [], True, False, len(results)
        )
    prov = frozenset(i for i, st in enumerate(p.stops) if st.opening.status == "provisional")
    if prov:
        for perm in perms:
            if _solve_perm(p, perm, _Relax(hours=prov)).status == "ok":
                return Solution(
                    "unverified",
                    order_refs,
                    [],
                    base_w | {"special_hours_unverified"},
                    [],
                    [{"code": "PROVISIONAL_HOURS_CONFLICT"}],
                    [],
                    True,
                    False,
                    len(results),
                )
    rep = results[0].order if results else tuple(range(n))
    if any(r.status == "no_route" for r in results) and all(r.status in ("no_route",) for r in results):
        codes, details = ["ROUTE_NOT_FOUND"], [{"code": "ROUTE_NOT_FOUND"}]
    else:
        codes, details = _diagnose(p, rep)
    suggest: list[str] = []
    if n > 1:
        for drop in range(n):
            if dl.expired():
                break
            rest = [i for i in range(n) if i != drop]
            sub = Problem(
                p.depart,
                p.ret,
                p.start_loc,
                p.end_loc,
                [p.stops[i] for i in rest],
                p.legs,
                p.nap,
                p.meals,
                p.global_warnings,
            )
            sub_perms = itertools.permutations(range(len(rest))) if mode == "auto" else [tuple(range(len(rest)))]
            if any(_solve_perm(sub, sp).status == "ok" for sp in sub_perms):
                suggest.append(p.stops[drop].ref)
    return Solution("infeasible", order_refs, [], base_w, codes, details, suggest, True, False, len(results))
