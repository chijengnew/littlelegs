"""候選搜尋、排序／可行性檢查與重新檢查的流程協調。

外部資料（Google 營業時間、天氣、車程）只供當次計算與回應，不寫入資料庫、日誌或快取。
每次外部嘗試都先取得出站額度（見 app.external.google）；整體查詢期限 30 秒涵蓋排隊與串接。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import update

from app.db.models import Place
from app.domain import ranking
from app.domain.hours import OpeningInfo, opening_for_date
from app.domain.ranking import REASON_TEMPLATES_ZH, WARNING_TEMPLATES_ZH, default_stay, evaluate
from app.domain.scheduler import UNVERIFIED_WARNINGS, Leg, Problem, Solution, StopSpec
from app.domain.schemas import Conditions, StopIn
from app.domain.solver_runner import SolverTimeout, run_solver
from app.domain.validation import check_departure_future, check_new_search_date, departure
from app.domain.weather import THRESHOLD, WeatherJudgement, describe_uncovered, judge, request_params
from app.domain.weather_areas import Area, AreaPoint, district_of, group_points
from app.errors import ApiError
from app.external.google import Deadline, GoogleError, MatrixElement
from app.geo import haversine_m
from app.ratelimit import QuotaExceeded, quota_api_error
from app.services import history as history_svc
from app.services.endpoints import ResolvedEndpoint, resolve
from app.services.places import PlaceData, candidates_within, load_places, lodging_near
from app.services.users import CurrentUser
from app.state import AppState
from app.timeutil import TPE, local_dt, local_today

log = logging.getLogger("littlelegs.planning")

CANDIDATE_RADIUS_M = 30_000
CANDIDATE_TOP = 15
LODGING_RADIUS_M = 10_000
LODGING_TOP = 10
RECHECK_MAX_OFFSET = 6

SOURCE_MAP_CANDIDATES = {
    "candidates[].name": "open_data",
    "candidates[].address": "open_data",
    "candidates[].location": "open_data",
    "candidates[].types": "open_data|manual",
    "candidates[].facilities": "open_data|manual",
    "candidates[].indoor": "open_data|manual",
    "candidates[].age": "open_data|manual|system",
    "candidates[].distance_m": "system",
    "candidates[].default_stay": "open_data|system",
    "candidates[].weather_area": "system",
    "weather": "google",
    "lodging[].name": "open_data",
    "lodging[].family_facilities": "open_data|manual",
    "lodging[].distance_m": "system",
}
SOURCE_MAP_PLAN = {
    "timeline[type=move]": "google",
    "timeline[type=attraction].stay": "open_data|system|user",
    "timeline[type=rest,reason=wait]": "system",
    "timeline[type=meal]": "system",
    "stops[].hours": "google",
    "weather": "google",
    "feasibility": "system",
    "stops[].name": "open_data",
}


@dataclass
class Ctx:
    st: AppState
    now: datetime
    deadline: Deadline
    user: CurrentUser | None

    @property
    def today(self) -> date:
        return local_today(self.now)


@dataclass
class AreaWeather:
    area: Area
    judgement: WeatherJudgement
    ok: bool


@dataclass
class WeatherResult:
    judgement: WeatherJudgement | None
    external_failed: bool = False
    areas: list[AreaWeather] = field(default_factory=list)
    rain_filter: bool = False
    index: dict[str, int] = field(default_factory=dict)

    def area_of(self, key: str) -> int | None:
        return self.index.get(key)

    def status_for(self, key: str) -> str:
        i = self.index.get(key)
        if i is not None:
            return self.areas[i].judgement.status
        return self.judgement.status if self.judgement else "not_requested"

    def triggered_for(self, key: str) -> bool:
        return self.rain_filter and self.status_for(key) == "triggered"

    @property
    def used_google(self) -> bool:
        return any(x.judgement.parts for x in self.areas) or (self.judgement is not None and bool(self.judgement.parts))


def _area_points(start: ResolvedEndpoint, end: ResolvedEndpoint, places: list[PlaceData]) -> list[AreaPoint]:
    pts = [AreaPoint("start", start.lat, start.lon, district_of(start.place_address))]
    pts += [AreaPoint(p.ref, p.lat, p.lon, district_of(p.address, p.city)) for p in places]
    pts.append(AreaPoint("end", end.lat, end.lon, district_of(end.place_address)))
    return pts


async def _resolve_endpoints(ctx: Ctx, c: Conditions) -> tuple[ResolvedEndpoint, ResolvedEndpoint]:
    async with ctx.st.factory() as s:
        start = await resolve(ctx.st, s, c.start, ctx.user.id if ctx.user else None, ctx.deadline)
        end = (
            start if c.end is None else await resolve(ctx.st, s, c.end, ctx.user.id if ctx.user else None, ctx.deadline)
        )
    return start, end


async def _weather(ctx: Ctx, c: Conditions, points: list[AreaPoint]) -> WeatherResult:
    """出遊日在今天起 10 天內就查沿途天氣，不論是否勾選「下雨只排室內」；今天起第 10 天以後不呼叫。

    地點依距離分成最多 6 區、每區一次每日預報。勾選時各地點依所在區判斷是否只排室內，
    查詢失敗的區標為 unverified 並使結果成為 partial；沒勾選時失敗的區直接不列出。
    """
    rain = c.rain_indoor_only
    params = request_params(c.date, ctx.today)
    if params is None:
        if not rain:
            return WeatherResult(None)
        return WeatherResult(judge(None, c.date, c.t_depart, c.t_return, requested=False), rain_filter=True)

    async def lookup(a: Area) -> AreaWeather:
        days: list[dict] | None = None
        if ctx.st.google is not None:
            try:
                days = await ctx.st.google.daily_forecast(
                    a.lat, a.lon, params["days"], params["pageSize"], ctx.deadline
                )
            except (GoogleError, QuotaExceeded):
                days = None
        return AreaWeather(a, judge(days, c.date, c.t_depart, c.t_return), days is not None)

    found = list(await asyncio.gather(*(lookup(a) for a in group_points(points))))
    failed = any(not x.ok for x in found)
    areas = found if rain else [x for x in found if x.ok]
    index = {k: i for i, x in enumerate(areas) for k in x.area.keys}
    return WeatherResult(None, rain and failed, areas, rain, index)


async def _mark_place_id_not_found(ctx: Ctx, place_id: uuid.UUID) -> None:
    """使用時遇到 NOT_FOUND：暫停此地點的新候選，交由 Place ID 更新腳本以獨立來源重新搜尋。"""
    try:
        async with ctx.st.factory() as s, s.begin():
            await s.execute(
                update(Place)
                .where(Place.id == place_id, Place.place_id_status == "accepted")
                .values(place_id_status="not_found", updated_at=ctx.now)
            )
    except Exception:
        log.warning("place_id not_found 標記失敗", extra={"place": str(place_id)})


async def _hours(ctx: Ctx, places: list[PlaceData], target: date) -> tuple[dict[uuid.UUID, OpeningInfo], bool]:
    """平行取得營業資訊；回傳 (place → OpeningInfo, 是否有外部失敗)。缺 Place ID 者為 unknown。"""
    out: dict[uuid.UUID, OpeningInfo] = {}
    failed = False

    async def one(p: PlaceData):
        nonlocal failed
        if not p.google_place_id or p.place_id_status != "accepted" or ctx.st.google is None:
            out[p.id] = opening_for_date(None, target, ctx.today)
            return
        try:
            raw = await ctx.st.google.place_hours(p.google_place_id, ctx.deadline)
            out[p.id] = opening_for_date(raw, target, ctx.today)
        except GoogleError as e:
            out[p.id] = opening_for_date(None, target, ctx.today)
            if e.kind == "not_found":
                await _mark_place_id_not_found(ctx, p.id)
            else:
                failed = True
        except QuotaExceeded as e:
            info = opening_for_date(None, target, ctx.today)
            if e.window == "billing_month":
                info.notes.append("本月營業時間查詢額度已用完，營業時間未確認")
            out[p.id] = info
            failed = True

    await asyncio.gather(*(one(p) for p in places))
    return out, failed


def _iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.astimezone(TPE).isoformat()


def _warn_objs(codes) -> list[dict]:
    return [{"code": w, "message": WARNING_TEMPLATES_ZH.get(w, w)} for w in sorted(codes)]


def _reason_objs(codes: list[str], facilities: list[str] | None = None) -> list[dict]:
    fac_zh = {"stroller_friendly": "推車友善", "nursing_room": "哺乳室", "family_toilet": "親子廁所"}
    out = []
    for r in codes:
        msg = REASON_TEMPLATES_ZH.get(r, r)
        if r == "facility_match":
            msg = msg.format(facilities="、".join(fac_zh.get(f, f) for f in facilities or []))
        out.append({"code": r, "message": msg})
    return out


def _endpoint_out(r: ResolvedEndpoint, member: bool) -> dict:
    d: dict = {"type": r.kind, "label": r.label}
    if r.kind == "place_ref":
        d["place_id"] = r.place_ref
        d["removed"] = r.removed
        d["name"] = r.place_name
        d["address"] = r.place_address
        d["google_place_id"] = r.google_place_id
    elif r.kind == "google_place":
        d["google_place_id"] = r.google_place_id
        d["endpoint_id"] = r.private_endpoint_id
    elif r.kind == "device_coordinate":
        d["coordinate"] = {"lat": r.lat, "lng": r.lon}
    if member:
        d["location"] = {"lat": r.lat, "lng": r.lon, "source": r.coord_source, "persist": False}
    return d


def _facilities_out(p: PlaceData) -> dict:
    return {f: {"status": s, "confirmation": c} for f, (s, c) in sorted(p.facilities.items())}


def _hours_out(info: OpeningInfo | None) -> dict | None:
    if info is None:
        return None
    return {
        "status": info.status,
        "intervals": [[_iso(a), _iso(b)] for a, b in info.intervals],
        "notes": info.notes,
        "source": "google",
    }


def _parts_out(j: WeatherJudgement) -> list[dict]:
    return [
        {"label": p.label, "start": _iso(p.start), "end": _iso(p.end), "percent": p.percent, "type": p.ptype}
        for p in j.parts
    ]


def _weather_out(w: WeatherResult, keep: list[int] | None = None) -> dict | None:
    """頂層欄位沿用舊格式（parts 為起點所在區）；areas 為沿途分區，keep 指定要列出的區。"""
    shown = w.areas if keep is None else [w.areas[i] for i in keep]
    if not shown:
        j = w.judgement
        if j is None:
            return None
        return {
            "status": j.status,
            "max_precipitation_percent": j.max_percent,
            "threshold_percent": THRESHOLD,
            "location": "start",
            "note": j.note,
            "explanation": "含其他降水，各區以日間／夜間預報判斷",
            "parts": _parts_out(j),
            "uncovered": describe_uncovered(j),
            "source": "google",
            "rain_filter": w.rain_filter,
            "areas": [],
        }
    js = [x.judgement for x in shown]
    if any(j.status == "triggered" for j in js):
        status = "triggered"
    elif any(j.status == "unverified" for j in js):
        status = "unverified"
    else:
        status = "not_triggered"
    first = js[0]
    return {
        "status": status if w.rain_filter else "not_requested",
        "max_precipitation_percent": max((j.max_percent for j in js if j.max_percent is not None), default=None),
        "threshold_percent": THRESHOLD,
        "location": "start",
        "note": first.note,
        "explanation": "含其他降水，各區以日間／夜間預報判斷",
        "parts": _parts_out(first),
        "uncovered": describe_uncovered(first),
        "source": "google",
        "rain_filter": w.rain_filter,
        "areas": [
            {
                "label": x.area.label,
                "roles": [r for r in ("start", "end") if r in x.area.keys],
                "status": x.judgement.status,
                "max_precipitation_percent": x.judgement.max_percent,
                "parts": _parts_out(x.judgement),
                "uncovered": describe_uncovered(x.judgement),
                "note": x.judgement.note,
            }
            for x in shown
        ],
    }


def _map_hints(member: bool, n_stops: int) -> dict:
    if not member:
        return {"mode": "locked_illustration", "message": "登入後可查看地圖"}
    return {
        "mode": "google_map",
        "connect_line": n_stops >= 2,
        "line_note": "順序示意，非道路導航" if n_stops >= 2 else None,
    }


async def candidate_search(st: AppState, user: CurrentUser | None, query_id: str, c: Conditions) -> dict:
    now = st.clock()
    check_new_search_date(c, now)
    check_departure_future(c, now)
    ctx = Ctx(st, now, Deadline(st.settings.limits.request_deadline_s), user)
    qid = uuid.UUID(query_id)
    hist: tuple[uuid.UUID, uuid.UUID] | None = None
    if user is not None:
        hist = await history_svc.begin_search(st.factory, user.id, qid, c, now)

    try:
        result = await _candidate_core(ctx, c)
    except (ApiError, QuotaExceeded) as e:
        if hist is not None:
            await history_svc.finish_search(st.factory, hist[0], hist[1], "failed", None, st.clock())
        if isinstance(e, QuotaExceeded):
            raise quota_api_error(e) from e
        raise

    status = "partial" if result["operation"] == "partial" else "succeeded"
    revision = None
    if hist is not None:
        await history_svc.finish_search(st.factory, hist[0], hist[1], status, None, st.clock())
        revision = await _history_revision(st, hist[0])
    result.update(
        {
            "query_id": query_id,
            "history": None if hist is None else {"id": str(hist[0]), "status": status, "revision": revision},
            "map": _map_hints(user is not None, 0),
            "field_sources": SOURCE_MAP_CANDIDATES,
            "attributions": ["Google Maps"] if result.pop("_google_used") else [],
        }
    )
    return result


async def _history_revision(st: AppState, hid: uuid.UUID) -> int | None:
    from app.db.models import History

    async with st.factory() as s:
        h = await s.get(History, hid)
        return None if h is None else h.revision


async def _candidate_core(ctx: Ctx, c: Conditions) -> dict:
    member = ctx.user is not None
    start, end = await _resolve_endpoints(ctx, c)
    google_used = start.coord_source == "google" or end.coord_source == "google"
    async with ctx.st.factory() as s:
        pool = await candidates_within(s, start.lat, start.lon, CANDIDATE_RADIUS_M)
        lodging = await lodging_near(s, end.lat, end.lon, LODGING_RADIUS_M)

    evals = []
    for p, d in pool:
        ev = evaluate(p, d, c.children_ages, c.facility_prefs, c.type_prefs)
        if ev.age == "unsuitable":
            continue
        evals.append(ev)

    near_first = sorted(evals, key=lambda e: e.distance_m)
    weather = await _weather(ctx, c, _area_points(start, end, [e.place for e in near_first]))
    google_used |= weather.used_google
    evals = [
        e
        for e in evals
        if not weather.triggered_for(e.place.ref) or e.indoor_state in ("indoor_confirmed", "indoor_inferred")
    ]
    evals.sort(key=ranking.initial_rank_key)
    top = evals[:CANDIDATE_TOP]
    top.sort(key=ranking.rerank_key)

    keys = ["start", "end", *(e.place.ref for e in top)]
    keep = sorted({i for k in keys if (i := weather.area_of(k)) is not None})
    pos = {i: n for n, i in enumerate(keep)}
    out = []
    for ev in top:
        p = ev.place
        reasons, warnings = ranking.reasons_and_warnings(
            ev, weather_status=weather.status_for(p.ref), rain_checked=c.rain_indoor_only, hours_checked=False
        )
        stay, stay_src = default_stay(p, None)
        item = {
            "place_id": p.ref,
            "google_place_id": p.google_place_id,
            "name": p.name,
            "address": p.address,
            "city": p.city,
            "distance_m": round(ev.distance_m),
            "distance_note": "直線距離，非開車距離",
            "primary_type": p.primary_type,
            "types": p.types,
            "indoor": {"value": p.indoor, "confirmation": p.indoor_confirmation},
            "facilities": _facilities_out(p),
            "age": ev.age,
            "age_range": None
            if ev.age_range is None
            else {"min_age": ev.age_range[0], "max_age": ev.age_range[1], "confirmation": "estimated"},
            "default_stay": {"minutes": stay, "source": stay_src, "estimated": True},
            "reasons": _reason_objs(reasons, ev.facility_hits),
            "warnings": _warn_objs(set(warnings)),
        }
        area = weather.area_of(p.ref)
        item["weather_area"] = None if area is None else pos[area]
        if member:
            item["location"] = {"lat": p.lat, "lng": p.lon, "source": "open_data"}
        out.append(item)

    lodging_out = _lodging(lodging, member)
    operation = "partial" if weather.external_failed else ("ok" if out else "no_results")
    return {
        "operation": operation,
        "start": _endpoint_out(start, member),
        "end": _endpoint_out(end, member),
        "weather": _weather_out(weather, keep),
        "candidates": out,
        "candidate_count": len(out),
        "lodging": lodging_out,
        "_google_used": google_used,
        "notices": ["車程、停車、餐飲與步行請出發前自行確認"],
    }


def _lodging(rows: list[tuple[PlaceData, float]], member: bool) -> dict:
    """終點 10 km 內最多 10 筆；依已確認親子設施數、距離、內部 ID 排序；不呼叫 Routes。"""
    fam = ("crib", "baby_bathtub", "kids_play_area")

    def confirmed(p: PlaceData) -> list[str]:
        return [f for f in fam if p.facilities.get(f) == ("yes", "confirmed")]

    rows = [(p, d) for p, d in rows if p.license_verified]
    rows.sort(key=lambda t: (-len(confirmed(t[0])), t[1], t[0].id.bytes))
    items = []
    for p, d in rows[:LODGING_TOP]:
        facs = confirmed(p)
        it: dict[str, Any] = {
            "place_id": p.ref,
            "name": p.name,
            "address": p.address,
            "distance_m": round(d),
            "distance_note": "直線距離，非開車距離",
            "family_facilities": facs,
            "label": "有親子設施資訊" if facs else "親子設施未確認",
        }
        if member:
            it["location"] = {"lat": p.lat, "lng": p.lon, "source": "open_data"}
        items.append(it)
    return {"items": items, "empty": not items, "note": None if items else "附近沒有授權已核對的旅宿資料"}


@dataclass
class StopPlan:
    place: PlaceData
    stay: int
    stay_source: str


@dataclass
class PlanOutcome:
    solution: Solution
    stops: list[StopPlan]
    start: ResolvedEndpoint
    end: ResolvedEndpoint
    loc_refs: dict[int, str]
    weather: WeatherResult
    hours: dict[uuid.UUID, OpeningInfo]
    operation: str
    reasons: dict = field(default_factory=dict)


def _loc_key(r: ResolvedEndpoint) -> str:
    if r.kind == "place_ref":
        return f"place:{r.place_ref}"
    if r.kind == "google_place":
        return f"gplace:{r.google_place_id}"
    return f"coord:{r.lat!r},{r.lon!r}"


async def _load_stops(ctx: Ctx, stops: list[StopIn], stay_sources: list[str] | None = None) -> list[StopPlan]:
    async with ctx.st.factory() as s:
        places = await load_places(s, [uuid.UUID(x.place_id) for x in stops])
    out = []
    for i, x in enumerate(stops):
        p = places.get(uuid.UUID(x.place_id))
        if p is None or p.kind != "attraction":
            raise ApiError(422, "STOP_NOT_FOUND", "找不到選取的景點", errors=[{"loc": ["stops", str(i)]}])
        if x.stay_minutes is not None and stay_sources is not None:
            stay, src = x.stay_minutes, stay_sources[i]
        else:
            stay, src = default_stay(p, x.stay_minutes)
        out.append(StopPlan(p, stay, src))
    return out


async def _plan_core(ctx: Ctx, c: Conditions, stops: list[StopPlan], mode: str) -> PlanOutcome:
    start, end = await _resolve_endpoints(ctx, c)
    keys: dict[str, int] = {}
    coords: list[tuple[float, float]] = []
    refs: dict[int, str] = {}

    def idx(key: str, lat: float, lon: float, ref: str) -> int:
        if key not in keys:
            keys[key] = len(coords)
            coords.append((lat, lon))
            refs[keys[key]] = ref
        return keys[key]

    s_i = idx(_loc_key(start), start.lat, start.lon, "start")
    e_i = idx(_loc_key(end), end.lat, end.lon, "end" if _loc_key(end) != _loc_key(start) else "start")
    stop_locs = [idx(f"place:{sp.place.ref}", sp.place.lat, sp.place.lon, sp.place.ref) for sp in stops]

    async def matrix() -> tuple[dict[tuple[int, int], MatrixElement] | None, bool]:
        if len(coords) < 2:
            return {}, False
        if ctx.st.google is None:
            return None, True
        try:
            return await ctx.st.google.route_matrix(coords, ctx.deadline), False
        except (GoogleError, QuotaExceeded):
            return None, True

    weather_t = asyncio.create_task(_weather(ctx, c, _area_points(start, end, [sp.place for sp in stops])))
    hours_t = asyncio.create_task(_hours(ctx, [sp.place for sp in stops], c.date))
    matrix_t = asyncio.create_task(matrix())
    weather = await weather_t
    hours, hours_failed = await hours_t
    mat, mat_failed = await matrix_t

    legs: dict[tuple[int, int], Leg] = {}
    if mat:
        for (i, j), el in mat.items():
            legs[(i, j)] = Leg(el.status, el.seconds, el.meters)

    gw: set[str] = set()
    if c.rain_indoor_only and any(weather.status_for(sp.place.ref) == "unverified" for sp in stops):
        gw.add("weather_unverified")
    specs = []
    start_dist_src = start.coord_source
    reasons: dict[str, list[str]] = {}
    for sp, loc in zip(stops, stop_locs, strict=True):
        p = sp.place
        ev = evaluate(
            p, haversine_m(start.lat, start.lon, p.lat, p.lon), c.children_ages, c.facility_prefs, c.type_prefs
        )
        warns: set[str] = set()
        viol: set[str] = set()
        if ev.age == "unsuitable":
            viol.add("AGE_UNSUITABLE")
        if weather.triggered_for(p.ref):
            if ev.indoor_state == "indoor_inferred":
                warns.add("indoor_inferred")
            elif ev.indoor_state != "indoor_confirmed":
                viol.add("INDOOR_REQUIRED")
        if p.removed:
            warns.add("place_removed")
        r, _ = ranking.reasons_and_warnings(ev, weather_status="not_requested", rain_checked=False)
        reasons[p.ref] = ranking.persistable_reasons(r, start_dist_src)
        specs.append(StopSpec(p.ref, loc, sp.stay, sp.stay_source, hours[p.id], warns, viol))

    problem = Problem(
        local_dt(c.date, c.t_depart),
        local_dt(c.date, c.t_return),
        s_i,
        e_i,
        specs,
        legs,
        None if c.nap is None else (local_dt(c.date, c.nap.t_start), local_dt(c.date, c.nap.t_end)),
        [
            (name, local_dt(c.date, w.t_start), local_dt(c.date, w.t_end))
            for name, w in (("lunch", c.lunch), ("dinner", c.dinner))
            if w is not None
        ],
        gw,
    )
    lim = ctx.st.settings.limits
    try:
        sol = await run_solver(problem, mode, lim.algorithm_budget_s, ctx.deadline.remaining())
    except SolverTimeout:
        refs_order = [sp.place.ref for sp in stops]
        warns = {"search_incomplete"} | gw
        for s_ in specs:
            warns |= s_.warnings
        sol = Solution("unverified", refs_order, [], warns, [], [], [], False, False, 0)
    operation = "partial" if (hours_failed or mat_failed or weather.external_failed) else "ok"
    return PlanOutcome(sol, stops, start, end, refs, weather, hours, operation, reasons)


def _timeline_out(sol: Solution, loc_refs: dict[int, str], names: dict[str, str]) -> list[dict]:
    out = []
    for it in sol.items:
        d: dict[str, Any] = {
            "type": it.type,
            "start": _iso(it.start),
            "end": _iso(it.end),
            "estimated": it.estimated,
            "source": it.source,
        }
        if it.type == "attraction":
            d["place_id"] = it.place_ref
            d["name"] = names.get(it.place_ref or "")
        elif it.type == "move":
            d["from"] = loc_refs.get(it.from_loc, "?") if it.from_loc is not None else "?"
            d["to"] = loc_refs.get(it.to_loc, "?") if it.to_loc is not None else "?"
            d["duration_s"] = it.travel_seconds
            d["distance_m"] = it.distance_m
        elif it.type == "meal":
            d["meal"] = it.meal
            d["at"] = loc_refs.get(it.to_loc, "?") if it.to_loc is not None else "?"
            d["note"] = "未指定餐廳，請自行確認用餐地點"
        elif it.type == "rest":
            d["reason"] = it.reason
            if it.reason == "nap":
                d["note"] = "午睡時段（可在車上或休息，不代表已找到休息設施）"
        out.append(d)
    return out


def _plan_response(ctx: Ctx, o: PlanOutcome, query_id: str, history: dict | None, mode: str) -> dict:
    member = ctx.user is not None
    sol = o.solution
    names = {sp.place.ref: sp.place.name for sp in o.stops}
    by_ref = {sp.place.ref: sp for sp in o.stops}
    stops_out = []
    for ref in sol.order:
        sp = by_ref[ref]
        it = {
            "place_id": ref,
            "name": sp.place.name,
            "address": sp.place.address,
            "google_place_id": sp.place.navigation_place_id,
            "primary_type": sp.place.primary_type,
            "stay_minutes": sp.stay,
            "stay_source": sp.stay_source,
            "estimated": sp.stay_source != "user",
            "hours": _hours_out(o.hours.get(sp.place.id)),
            "removed": sp.place.removed,
        }
        if member:
            it["location"] = {"lat": sp.place.lat, "lng": sp.place.lon, "source": "open_data"}
        stops_out.append(it)
    google_used = bool(sol.items) or any(h.status != "unknown" for h in o.hours.values()) or o.weather.used_google
    return {
        "query_id": query_id,
        "mode": mode,
        "operation": o.operation,
        "feasibility": sol.feasibility,
        "feasibility_note": {
            "feasible": "依來源資料與估計值可行，非現場或交通保證",
            "unverified": "沒有已知違反，但必要資料缺漏或涵蓋不足",
            "infeasible": "有已知的硬性條件違反",
        }[sol.feasibility],
        "order": sol.order,
        "stops": stops_out,
        "timeline": _timeline_out(sol, o.loc_refs, names),
        "warnings": _warn_objs(sol.warnings),
        "violation_codes": sol.violation_codes,
        "violations": sol.violation_details,
        "suggest_remove": sol.suggest_remove,
        "search": {
            "complete": sol.search_complete,
            "optimal_claimed": sol.optimal_claimed,
            "permutations_evaluated": sol.perms_evaluated,
            "note": "搜尋空間為 MVP 離散模型（以分鐘為單位），不宣稱為所有現實安排的全域最佳解",
        },
        "start": _endpoint_out(o.start, member),
        "end": _endpoint_out(o.end, member),
        "weather": _weather_out(o.weather),
        "history": history,
        "map": _map_hints(member, len(sol.order)),
        "field_sources": SOURCE_MAP_PLAN,
        "attributions": ["Google Maps"] if google_used else [],
        "notices": ["車程為不含即時路況的估計值（DRIVE、TRAFFIC_UNAWARE）", "停車、餐飲與步行請自行確認"],
    }


async def plan(
    st: AppState,
    user: CurrentUser | None,
    query_id: str,
    c: Conditions,
    stops: list[StopIn],
    mode: str,
    expected_revision: int | None,
) -> dict:
    """mode='auto'（排序）或 'manual'（依使用者順序檢查，不偷偷排序）。每次都是無狀態請求、重新計算矩陣。"""
    now = st.clock()
    check_new_search_date(c, now)
    check_departure_future(c, now)
    if user is not None:
        await history_svc.precheck_revision(st.factory, user.id, uuid.UUID(query_id), expected_revision)
    ctx = Ctx(st, now, Deadline(st.settings.limits.request_deadline_s), user)
    sp = await _load_stops(ctx, stops)
    try:
        o = await _plan_core(ctx, c, sp, mode)
    except QuotaExceeded as e:
        raise quota_api_error(e) from e
    history = None
    if user is not None:
        by_ref = {x.place.ref: x for x in sp}
        stored = [
            history_svc.StoredStop(
                by_ref[r].place.id, by_ref[r].stay, by_ref[r].stay_source, by_ref[r].place.google_place_id
            )
            for r in o.solution.order
        ]
        res = await history_svc.update_plan(
            st.factory,
            user.id,
            uuid.UUID(query_id),
            c,
            stored,
            True,
            expected_revision,
            st.clock(),
            {"v": 1, "stops": o.reasons},
        )
        if res is not None:
            history = {"id": str(res[0]), "revision": res[1]}
    return _plan_response(ctx, o, query_id, history, mode)


def recheck_eligibility(c: Conditions, now: datetime) -> str | None:
    """回傳不能重算的原因；None 表示可對原條件完整重算。"""
    if departure(c) <= now:
        return "DEPARTURE_PASSED"
    off = (c.date - local_today(now)).days
    if off > RECHECK_MAX_OFFSET:
        return "OUTSIDE_EXTERNAL_COVERAGE"
    return None


async def recheck_saved(
    st: AppState, user: CurrentUser, query_label: str, c: Conditions, stops: list[StopIn], stay_sources: list[str]
) -> dict:
    """開啟歷史／收藏的重算：只更新當次畫面，不改寫原條件、原採用順序或收藏內容。"""
    now = st.clock()
    why = recheck_eligibility(c, now)
    if why is not None:
        return {
            "rechecked": False,
            "reason": why,
            "message": {
                "DEPARTURE_PASSED": "原出發時間已過，未重新驗證；可選擇新日期重新規劃",
                "OUTSIDE_EXTERNAL_COVERAGE": "原日期超出天氣與特殊營業時間的涵蓋範圍（今天起 7 天），未重新驗證",
            }[why],
        }
    ctx = Ctx(st, now, Deadline(st.settings.limits.request_deadline_s), user)
    sp = await _load_stops(ctx, stops, stay_sources)
    try:
        o = await _plan_core(ctx, c, sp, "manual")
    except QuotaExceeded as e:
        raise quota_api_error(e) from e
    resp = _plan_response(ctx, o, query_label, None, "manual")
    resp["rechecked"] = True
    resp["checked_at"] = _iso(now)
    return resp


__all__ = ["candidate_search", "plan", "recheck_saved", "recheck_eligibility", "UNVERIFIED_WARNINGS"]
