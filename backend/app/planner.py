import math
from dataclasses import dataclass, field
from itertools import permutations

from data import PLACES_BY_ID
from models import ItineraryResponse, Note, Place, SearchConditions, Stop, to_hhmm, to_minutes

MAX_STOPS = 5
ROAD_FACTOR = 1.3
SPEED_KMH = {"car": 30.0, "transit": 18.0}
BUFFER_MINUTES = {"car": 10, "transit": 15}
LUNCH_MINUTES = 60


def haversine_km(a: Place, b: Place) -> float:
    radius = 6371.0
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat = lat2 - lat1
    dlng = math.radians(b.lng - a.lng)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def travel_minutes(a: Place, b: Place, transport: str) -> int:
    if a.id == b.id:
        return 0
    km = haversine_km(a, b) * ROAD_FACTOR
    return round(km / SPEED_KMH[transport] * 60 + BUFFER_MINUTES[transport])


def _overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def _place_params(place: Place) -> dict[str, str | int]:
    return {"place": place.name, "placeEn": place.name_en}


@dataclass
class _Simulation:
    stops: list[Stop]
    used: int
    end: int
    cost: float
    notes: list[Note] = field(default_factory=list)


def _simulate(order: tuple[Place, ...], conditions: SearchConditions) -> _Simulation | None:
    parent, child = conditions.parent, conditions.child
    start = to_minutes(parent.start_time)
    limit = start + parent.available_minutes
    nap = (to_minutes(child.nap_start), to_minutes(child.nap_end)) if child.nap_start and child.nap_end else None
    lunch_start = to_minutes(child.lunch_time)
    lunch = (lunch_start, lunch_start + LUNCH_MINUTES)

    now, used, penalty = start, 0, 0.0
    stops: list[Stop] = []
    notes: list[Note] = []
    previous: Place | None = None

    for place in order:
        travel = 0
        if previous is not None:
            travel = travel_minutes(previous, place, parent.transport)
            leg = (now, now + travel)
            if nap and (minutes := _overlap(*leg, *nap)):
                notes.append(Note(code="nap_in_transit", params={"minutes": minutes}))
            if minutes := _overlap(*leg, *lunch):
                penalty += minutes
                notes.append(Note(code="lunch_in_transit", params={"minutes": minutes}))
            now += travel
            used += travel

        opens, closes = to_minutes(place.open_time), to_minutes(place.close_time)
        if now < opens:
            wait = opens - now
            penalty += wait
            notes.append(Note(code="wait_open", params={**_place_params(place), "open": place.open_time, "minutes": wait}))
            now = opens

        arrive, leave = now, now + place.stay_minutes
        if leave > closes:
            return None

        if nap and (minutes := _overlap(arrive, leave, *nap)):
            if place.calm:
                notes.append(Note(code="nap_at_calm", params=_place_params(place)))
            else:
                penalty += minutes
                notes.append(Note(code="nap_noisy", params=_place_params(place)))
        if _overlap(arrive, leave, *lunch):
            if place.has_food:
                notes.append(Note(code="lunch_at", params=_place_params(place)))
            else:
                penalty += _overlap(arrive, leave, *lunch) / 2
                notes.append(Note(code="lunch_no_food", params=_place_params(place)))

        used += place.stay_minutes
        stops.append(Stop(place=place, arrive=to_hhmm(arrive), leave=to_hhmm(leave), travel_minutes_from_prev=travel))
        now, previous = leave, place

    if used > parent.available_minutes or now > limit:
        return None
    return _Simulation(stops=stops, used=used, end=now, cost=(now - start) + penalty, notes=notes)


def _used_minutes(order: tuple[Place, ...], transport: str) -> int:
    stay = sum(place.stay_minutes for place in order)
    travel = sum(travel_minutes(a, b, transport) for a, b in zip(order, order[1:]))
    return stay + travel


def plan_itinerary(conditions: SearchConditions, place_ids: list[str]) -> ItineraryResponse:
    available = conditions.parent.available_minutes
    ids = list(dict.fromkeys(place_ids))

    if len(ids) > MAX_STOPS:
        return ItineraryResponse(feasible=False, reason=Note(code="too_many", params={"max": MAX_STOPS}),
                                 available_minutes=available)
    places = [PLACES_BY_ID[place_id] for place_id in ids if place_id in PLACES_BY_ID]
    if len(places) != len(ids):
        return ItineraryResponse(feasible=False, reason=Note(code="unknown_place"), available_minutes=available)

    best: _Simulation | None = None
    min_used = math.inf
    for order in permutations(places):
        min_used = min(min_used, _used_minutes(order, conditions.parent.transport))
        simulation = _simulate(order, conditions)
        if simulation and (best is None or simulation.cost < best.cost):
            best = simulation

    if best is None:
        if min_used > available:
            reason = Note(code="over_time", params={"used": int(min_used), "available": available})
        else:
            reason = Note(code="hours_conflict")
        return ItineraryResponse(feasible=False, reason=reason, available_minutes=available)

    head = [Note(code="single_stop")] if len(places) == 1 else [Note(code="ordered_by_rules")]
    return ItineraryResponse(
        feasible=True,
        stops=best.stops,
        used_minutes=best.used,
        available_minutes=available,
        end_time=to_hhmm(best.end),
        notes=head + best.notes,
    )