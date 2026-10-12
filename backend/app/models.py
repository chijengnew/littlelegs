from datetime import date as Date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator
from pydantic.alias_generators import to_camel

TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"
TimeStr = Annotated[str, StringConstraints(pattern=TIME_PATTERN)]

CountyId = Literal["taipei", "new-taipei", "taoyuan", "hsinchu", "taichung", "tainan", "kaohsiung", "yilan"]
Transport = Literal["car", "transit"]


def to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def to_hhmm(minutes: int | float) -> str:
    value = max(0, int(round(minutes)))
    return f"{value // 60:02d}:{value % 60:02d}"


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ChildContext(CamelModel):
    ages: list[int] = Field(min_length=1, max_length=6)
    nap_start: TimeStr | None = None
    nap_end: TimeStr | None = None
    lunch_time: TimeStr = "12:00"

    @field_validator("ages")
    @classmethod
    def check_ages(cls, value: list[int]) -> list[int]:
        if any(age < 0 or age > 12 for age in value):
            raise ValueError("ages must be between 0 and 12")
        return value

    @model_validator(mode="after")
    def check_nap(self) -> "ChildContext":
        if (self.nap_start is None) != (self.nap_end is None):
            raise ValueError("napStart and napEnd must both be set or both be empty")
        if self.nap_start and self.nap_end and to_minutes(self.nap_end) <= to_minutes(self.nap_start):
            raise ValueError("napEnd must be later than napStart")
        return self


class ParentConstraints(CamelModel):
    county: CountyId
    date: Date
    start_time: TimeStr
    available_minutes: int = Field(ge=60, le=600)
    transport: Transport
    need_stroller: bool = False
    need_nursing_room: bool = False
    prefer_indoor: bool = False

    @model_validator(mode="after")
    def check_not_past_midnight(self) -> "ParentConstraints":
        if to_minutes(self.start_time) + self.available_minutes > 24 * 60:
            raise ValueError("startTime + availableMinutes must not pass midnight")
        return self


class SearchConditions(CamelModel):
    child: ChildContext
    parent: ParentConstraints


class Place(CamelModel):
    id: str
    name: str
    name_en: str
    county: CountyId
    lat: float
    lng: float
    indoor: bool
    age_min: int
    age_max: int
    stay_minutes: int
    open_time: TimeStr
    close_time: TimeStr
    closed_weekdays: list[int]
    stroller_friendly: bool
    nursing_room: bool
    has_food: bool
    calm: bool
    description: str


class Weather(CamelModel):
    summary: Literal["sunny", "cloudy", "rain"]
    rain_probability: int
    temperature_c: int


class Note(CamelModel):
    code: str
    params: dict[str, str | int] = Field(default_factory=dict)


class RecommendedPlace(CamelModel):
    place: Place
    score: int
    reasons: list[Note]


class RecommendationResponse(CamelModel):
    query_id: str
    conditions: SearchConditions
    weather: Weather
    results: list[RecommendedPlace]


class ItineraryRequest(CamelModel):
    conditions: SearchConditions
    place_ids: list[str] = Field(min_length=1, max_length=10)


class Stop(CamelModel):
    place: Place
    arrive: TimeStr
    leave: TimeStr
    travel_minutes_from_prev: int


class ItineraryResponse(CamelModel):
    feasible: bool
    reason: Note | None = None
    stops: list[Stop] = Field(default_factory=list)
    used_minutes: int = 0
    available_minutes: int
    end_time: TimeStr | None = None
    notes: list[Note] = Field(default_factory=list)


class HistoryCreate(CamelModel):
    query_id: str
    conditions: SearchConditions
    weather: Weather
    results: list[RecommendedPlace]


class HistoryRecord(HistoryCreate):
    created_at: str


class FavoriteCreate(CamelModel):
    conditions: SearchConditions
    itinerary: ItineraryResponse

    @model_validator(mode="after")
    def check_feasible(self) -> "FavoriteCreate":
        if not self.itinerary.feasible or not self.itinerary.stops:
            raise ValueError("only a feasible itinerary can be saved")
        return self


class FavoriteRecord(FavoriteCreate):
    id: str
    created_at: str