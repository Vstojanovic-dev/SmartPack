"""Validated trip, packing and external-service data contracts."""
from datetime import date
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints, field_validator, model_validator

LUGGAGE_TYPES = ('Nahrbtnik', 'Kabinski kovček', 'Veliki kovček')
ACTIVITIES = ('Ogled mesta', 'Pohodništvo', 'Plavanje in plaža', 'Smučanje', 'Poslovno potovanje', 'Športne aktivnosti', 'Kampiranje', 'Večerni izhodi')
Text = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]
Duration = Annotated[StrictInt, Field(ge=1, le=60)]
Luggage = Literal['Nahrbtnik', 'Kabinski kovček', 'Veliki kovček']
Activity = Literal['Ogled mesta', 'Pohodništvo', 'Plavanje in plaža', 'Smučanje', 'Poslovno potovanje', 'Športne aktivnosti', 'Kampiranje', 'Večerni izhodi']


class ServiceError(Exception):
    """Safe, user-facing service failure (never contains credentials)."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class TripInput(StrictModel):
    destination: Text
    departure_date: date
    duration_days: Duration
    luggage_type: Luggage
    max_weight_kg: Annotated[float, Field(gt=0, allow_inf_nan=False)] | None = None
    activities: list[Activity] = Field(default_factory=list, strict=True)

    @field_validator('departure_date')
    @classmethod
    def future_departure(cls, value):
        if value < date.today():
            raise ValueError('Datum odhoda ne sme biti v preteklosti.')
        return value

    @field_validator('max_weight_kg', mode='before')
    @classmethod
    def numeric_weight(cls, value):
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise ValueError('Masa mora biti pozitivno število.')
        return value


class PackingItem(StrictModel):
    name: Text
    quantity: Annotated[StrictInt, Field(gt=0)]
    unit: Text
    reason: Text


def check_duplicates(items):
    names = [' '.join(item.name.casefold().split()) for item in items]
    if len(names) != len(set(names)):
        raise ValueError('Seznam vsebuje podvojene predmete.')


class PackingCategory(StrictModel):
    name: Text
    items: list[PackingItem] = Field(min_length=1)

    @model_validator(mode='after')
    def unique_items(self):
        check_duplicates(self.items)
        return self


class PackingRecommendation(StrictModel):
    destination: Text
    duration_days: Duration
    luggage_type: Luggage
    categories: list[PackingCategory] = Field(min_length=1)
    general_advice: list[Text] = Field(default_factory=list)

    @model_validator(mode='after')
    def unique_items(self):
        check_duplicates([item for category in self.categories for item in category.items])
        return self


class Location(StrictModel):
    name: Text
    formatted: Text
    country: Text
    latitude: Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
    longitude: Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]

    @field_validator('latitude', 'longitude', mode='before')
    @classmethod
    def numeric_coordinate(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError('Koordinata mora biti število.')
        return value


class WeatherDay(StrictModel):
    date: date
    temperature_2m_min: float
    temperature_2m_max: float
    precipitation_sum: float
    precipitation_probability_max: float | None = None
    weather_code: int
    wind_speed_10m_max: float


class WeatherForecast(StrictModel):
    status: Literal['complete', 'partial', 'unavailable']
    requested_start: date
    requested_end: date
    days: list[WeatherDay] = Field(default_factory=list)
    coverage_start: date | None = None
    coverage_end: date | None = None
    units: dict[str, str] = Field(default_factory=dict)
    message: str = ''
