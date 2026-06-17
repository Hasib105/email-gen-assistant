"""Case domain schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FlightSegment(BaseModel):
    model_config = ConfigDict(frozen=True)

    origin: str
    destination: str
    flight_number: str
    departure_date: str
    status: str


class TravelPreferences(BaseModel):
    model_config = ConfigDict(frozen=True)

    preferred_seat: str = ""
    meal_preference: str = ""
    frequent_flyer_number: str = ""
    preferred_airlines: list[str] = Field(default_factory=list)
    preferred_hotel_chain: str = ""
    notes: str = ""


class TravelHistoryEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    trip_id: str
    origin: str
    destination: str
    date: str
    status: str
    notes: str = ""


def _empty_flight_segments() -> list[FlightSegment]:
    return []


def _empty_messages() -> list[str]:
    return []


def _empty_travel_history() -> list[TravelHistoryEntry]:
    return []


class CaseRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    customer_name: str
    customer_email: str
    customer_phone: str
    customer_tier: str
    booking_reference: str
    issue_type: str
    summary: str
    requested_outcome: str
    itinerary: list[FlightSegment] = Field(default_factory=_empty_flight_segments)
    recent_messages: list[str] = Field(default_factory=_empty_messages)
    travel_preferences: TravelPreferences = Field(default_factory=TravelPreferences)
    travel_history: list[TravelHistoryEntry] = Field(default_factory=_empty_travel_history)


class CaseNotFoundError(Exception):
    """Raised when a case ID is not available to the assistant."""

    def __init__(self, case_id: str) -> None:
        super().__init__(f"Case not found: {case_id}")
        self.case_id = case_id
