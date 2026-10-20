from datetime import UTC, datetime, timedelta
from datetime import date as LocalDate
from datetime import time as LocalTime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from jarvis.calendar import CalendarService, DomainError
from jarvis.schemas import CalendarInput, EventDelete, EventInput, StrictModel


class Empty(StrictModel):
    pass


class EventQuery(StrictModel):
    date: LocalDate = Field(description="First LOCAL date to search, YYYY-MM-DD")
    timezone: str = "Asia/Singapore"
    days: int = Field(default=1, ge=1, le=31)
    query: str = ""
    calendar_id: str | None = None


class EventID(StrictModel):
    event_id: str


class LocalEvent(StrictModel):
    calendar_id: str
    title: str
    date: LocalDate = Field(description="LOCAL calendar date, YYYY-MM-DD. Never convert to UTC.")
    time: str = Field(
        pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$",
        description="LOCAL wall clock HH:MM only, e.g. 19:00 for 7 pm. No seconds or UTC offset.",
    )
    duration_minutes: int = Field(gt=0, le=10080)
    timezone: str = "Asia/Singapore"
    location: str = ""
    duration_is_estimate: bool = False
    utc_offset_minutes: int | None = Field(
        default=None, description="Only for an explicitly clarified DST offset"
    )

    def resolved(self):
        naive = datetime.combine(self.date, LocalTime.fromisoformat(self.time))
        tz = ZoneInfo(self.timezone)
        candidates = [naive.replace(tzinfo=tz, fold=f) for f in (0, 1)]
        valid = {
            c.utcoffset(): c
            for c in candidates
            if c.astimezone(UTC).astimezone(tz).replace(tzinfo=None) == naive
        }
        if self.utc_offset_minutes is not None:
            valid = {
                offset: c
                for offset, c in valid.items()
                if offset.total_seconds() == self.utc_offset_minutes * 60
            }
        if len(valid) != 1:
            raise ValueError(
                "Local time is ambiguous or nonexistent; clarify the date/time or DST offset"
            )
        start = next(iter(valid.values()))
        return EventInput(
            calendar_id=self.calendar_id,
            title=self.title,
            start=start,
            duration_minutes=self.duration_minutes,
            timezone=self.timezone,
            location=self.location,
            duration_is_estimate=self.duration_is_estimate,
        ).model_dump(mode="json")


class LocalEventChange(StrictModel):
    event_id: str
    expected_version: int
    event: LocalEvent


class CalendarChange(StrictModel):
    calendar_id: str
    expected_version: int
    calendar: CalendarInput


class CalendarDelete(StrictModel):
    calendar_id: str
    expected_version: int


DEFINITIONS: dict[str, tuple[type[BaseModel], str]] = {
    "calendar_list": (Empty, "List available calendars and permissions."),
    "event_list": (
        EventQuery,
        "Find events by LOCAL date and title; the application calculates the search interval.",
    ),
    "event_get": (
        EventID,
        "Read the exact event and its version before proposing an update/delete.",
    ),
    "event_propose_create": (
        LocalEvent,
        "Propose creating a timed event. Ask for missing time/duration.",
    ),
    "event_propose_update": (
        LocalEventChange,
        "Propose editing one identified event, preserving unchanged fields.",
    ),
    "event_propose_delete": (EventDelete, "Propose deleting one explicitly identified event."),
    "calendar_propose_create": (CalendarInput, "Propose a new local calendar."),
    "calendar_propose_update": (CalendarChange, "Propose a local calendar metadata change."),
    "calendar_propose_delete": (
        CalendarDelete,
        "Preview deleting an app-created local calendar and its events.",
    ),
}


class ToolRegistry:
    def __init__(self, service: CalendarService):
        self.service = service

    def definitions(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": schema.model_json_schema(),
                },
            }
            for name, (schema, description) in DEFINITIONS.items()
        ]

    def call(self, name, arguments):
        if name not in DEFINITIONS:
            return {"status": "unknown_tool", "message": "Tool is not available"}
        schema = DEFINITIONS[name][0]
        try:
            parsed = schema.model_validate(arguments)
            args = parsed.model_dump(mode="json")
            if name == "calendar_list":
                result = self.service.calendars()
            elif name == "event_list":
                start = datetime.combine(parsed.date, LocalTime(), ZoneInfo(parsed.timezone))
                args = {
                    "start": start.isoformat(),
                    "end": (start + timedelta(days=parsed.days)).isoformat(),
                    "query": parsed.query,
                    "calendar_id": parsed.calendar_id,
                }
                result = self.service.events(**args)
            elif name == "event_get":
                result = self.service.get_event(**args)
            else:
                if isinstance(parsed, LocalEvent):
                    args = parsed.resolved()
                elif isinstance(parsed, LocalEventChange):
                    args["event"] = parsed.event.resolved()
                result = self.service.propose(name.replace("_propose", ""), args)
                return {"status": "pending_approval", "proposal": result}

            def display_times(item):
                if isinstance(item, dict) and "start" in item:
                    tz = ZoneInfo(item["timezone"])
                    start = datetime.fromisoformat(item["start"]).astimezone(tz)
                    end = datetime.fromisoformat(item["end"]).astimezone(tz)
                    return {
                        k: item[k]
                        for k in (
                            "id",
                            "calendar_id",
                            "title",
                            "timezone",
                            "location",
                            "duration_is_estimate",
                            "version",
                            "recurring",
                            "all_day",
                        )
                    } | {
                        "date": start.date().isoformat(),
                        "time": start.strftime("%H:%M"),
                        "duration_minutes": int((end - start).total_seconds() / 60),
                    }
                return item

            result = (
                [display_times(x) for x in result[:20]]
                if isinstance(result, list)
                else display_times(result)
            )
            return {"status": "ok", "data": result}
        except DomainError as e:
            return e.as_dict()
        except ValueError as e:
            return {"status": "needs_clarification", "message": str(e)[:1000]}


class InProcessTools:
    """Same registry for tests and explicit debugging; production default is MCP stdio."""

    def __init__(self, registry):
        self.registry = registry

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    async def definitions(self):
        return self.registry.definitions()

    async def call(self, name, arguments):
        return self.registry.call(name, arguments)
