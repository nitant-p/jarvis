from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EventInput(StrictModel):
    calendar_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    start: datetime
    duration_minutes: int = Field(gt=0, le=10080)
    timezone: str
    location: str = Field(default="", max_length=500)
    duration_is_estimate: bool = False

    @model_validator(mode="after")
    def validate_time(self):
        if not self.title.strip():
            raise ValueError("Title cannot be blank")
        try:
            tz = ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as e:
            raise ValueError("Use a valid IANA timezone") from e
        if self.start.utcoffset() is None:
            raise ValueError("Start must have an explicit UTC offset")
        local = self.start.astimezone(tz)
        # Reject mismatched offsets/nonexistent local wall times, preserving explicit DST folds.
        if local.replace(tzinfo=None) != self.start.replace(tzinfo=None):
            raise ValueError("Start offset does not match timezone at that local time")
        return self

    def event_fields(self):
        start = self.start.astimezone(UTC)
        return {
            **self.model_dump(exclude={"start", "duration_minutes"}),
            "start": start.isoformat(),
            "end": (start + timedelta(minutes=self.duration_minutes)).isoformat(),
        }


class EventChange(StrictModel):
    event_id: str
    expected_version: int = Field(ge=1)
    event: EventInput


class EventDelete(StrictModel):
    event_id: str
    expected_version: int = Field(ge=1)


class CalendarInput(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    timezone: str

    @model_validator(mode="after")
    def validate_calendar(self):
        if not self.name.strip():
            raise ValueError("Name cannot be blank")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as e:
            raise ValueError("Use a valid IANA timezone") from e
        return self


class ProposalRequest(StrictModel):
    operation: Literal[
        "event_create",
        "event_update",
        "event_delete",
        "calendar_create",
        "calendar_update",
        "calendar_delete",
    ]
    payload: dict


class Approval(StrictModel):
    allow_overlap: bool = False


class MessageInput(StrictModel):
    text: str = Field(min_length=1, max_length=4000)
    request_id: str = Field(min_length=1, max_length=100)
    conversation_id: str | None = None
    captured_at: datetime | None = None
    timezone: str = "Asia/Singapore"

    @model_validator(mode="after")
    def valid_capture(self):
        if not self.text.strip():
            raise ValueError("Message cannot be blank")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as e:
            raise ValueError("Use a valid IANA timezone") from e
        if self.captured_at and self.captured_at.utcoffset() is None:
            raise ValueError("Capture time must include an offset")
        return self
