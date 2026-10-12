from uuid import uuid4

from data import PLACES, fake_weather
from models import Note, Place, RecommendationResponse, RecommendedPlace, SearchConditions, Weather, to_minutes


def _is_candidate(place: Place, conditions: SearchConditions) -> bool:
    parent, child = conditions.parent, conditions.child
    start = to_minutes(parent.start_time)
    end = start + parent.available_minutes

    if place.county != parent.county:
        return False
    if parent.date.weekday() in place.closed_weekdays:
        return False
    if any(age < place.age_min or age > place.age_max for age in child.ages):
        return False
    if parent.need_stroller and not place.stroller_friendly:
        return False
    if parent.need_nursing_room and not place.nursing_room:
        return False
    window = min(end, to_minutes(place.close_time)) - max(start, to_minutes(place.open_time))
    return window >= place.stay_minutes


def _score(place: Place, conditions: SearchConditions, weather: Weather) -> tuple[int, list[Note]]:
    parent = conditions.parent
    rain = weather.rain_probability
    score = 50
    reasons = [Note(code="age_fit", params={"min": place.age_min, "max": place.age_max})]

    if place.indoor:
        if rain >= 60:
            score += 15
            reasons.append(Note(code="indoor_rain", params={"rain": rain}))
        elif parent.prefer_indoor:
            score += 10
            reasons.append(Note(code="indoor_pref"))
    else:
        if rain >= 60:
            score -= 20
            reasons.append(Note(code="outdoor_rain_risk", params={"rain": rain}))
        elif parent.prefer_indoor:
            score -= 10
        elif rain < 30:
            score += 10
            reasons.append(Note(code="outdoor_good_weather"))

    if parent.need_stroller and place.stroller_friendly:
        score += 5
        reasons.append(Note(code="stroller"))
    if parent.need_nursing_room and place.nursing_room:
        score += 5
        reasons.append(Note(code="nursing_room"))
    if place.has_food:
        score += 5
        reasons.append(Note(code="food"))
    if min(conditions.child.ages) < 3 and place.age_min == 0:
        score += 5
    if place.stay_minutes <= parent.available_minutes / 2:
        score += 5

    reasons.append(Note(code="open_hours", params={"open": place.open_time, "close": place.close_time}))
    reasons.append(Note(code="stay", params={"stay": place.stay_minutes}))
    return max(0, min(100, score)), reasons


def recommend(conditions: SearchConditions) -> RecommendationResponse:
    weather = fake_weather(conditions.parent.county, conditions.parent.date)
    results: list[RecommendedPlace] = []
    for place in PLACES:
        if not _is_candidate(place, conditions):
            continue
        score, reasons = _score(place, conditions, weather)
        results.append(RecommendedPlace(place=place, score=score, reasons=reasons))
    results.sort(key=lambda item: item.score, reverse=True)
    return RecommendationResponse(query_id=uuid4().hex, conditions=conditions, weather=weather, results=results)