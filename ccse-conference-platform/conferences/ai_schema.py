"""Candidate contract consumed by the existing approval service."""
from datetime import date, time
from decimal import Decimal
from typing import Generic, TypeVar, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
T = TypeVar("T")
class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
class EvidenceField(StrictModel, Generic[T]):
    value: T | None
    evidence: str | None
class ConferenceFields(StrictModel):
    conference_name: EvidenceField[str]
    organizer: EvidenceField[str]
    year: EvidenceField[int]
    start_date: EvidenceField[date]
    end_date: EvidenceField[date]
    start_time: EvidenceField[time]
    timezone: EvidenceField[str]
    location: EvidenceField[str]
    attendance_format: EvidenceField[Literal["in_person", "virtual", "hybrid"]]
    themes: EvidenceField[list[str]]
    target_audience: EvidenceField[list[str]]
class ExtractedDeadline(StrictModel):
    type: str = Field(min_length=1, max_length=64)
    date: date
    time: time | None
    timezone: str | None
    evidence: str = Field(min_length=1)
class ExtractedPrice(StrictModel):
    category: str = Field(min_length=1, max_length=128)
    rate_type: str = Field(min_length=1, max_length=64)
    amount: Decimal = Field(ge=0, le=Decimal("999999.99"), decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    evidence: str = Field(min_length=1)
class ExtractionResult(StrictModel):
    fields: ConferenceFields
    deadlines: list[ExtractedDeadline]
    registration_prices: list[ExtractedPrice]
    warnings: list[str]
    @model_validator(mode="after")
    def check_dates(self):
        f = self.fields
        if f.year.value is not None and not 1900 <= f.year.value <= 2200:
            raise ValueError("Invalid edition year")
        start, end = f.start_date.value, f.end_date.value
        if start and end and end < start:
            raise ValueError("End date precedes start date")
        for d in (start, end):
            if d and f.year.value and d.year != f.year.value:
                raise ValueError("Conference date conflicts with edition year")
        return self
