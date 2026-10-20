from datetime import UTC, datetime, timedelta

from pydantic import ValidationError
from sqlalchemy import select

from jarvis.db import Audit, Calendar, Event, Job, Proposal, record, uid
from jarvis.schemas import CalendarInput, EventChange, EventDelete, EventInput


class DomainError(Exception):
    def __init__(self, code, message, details=None, http_status=409):
        self.code, self.message, self.details = code, message, details
        self.http_status = http_status
        super().__init__(message)

    def as_dict(self):
        return {"status": self.code, "message": self.message, "details": self.details}


def instant(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
        if dt.utcoffset() is None:
            raise ValueError()
        return dt.astimezone(UTC).isoformat()
    except (ValueError, TypeError) as e:
        raise DomainError(
            "invalid_time", "Use an ISO timestamp with an offset", http_status=422
        ) from e


class CalendarService:
    def __init__(self, db, source_job_id=None):
        self.db = db
        self.source_job_id = source_job_id

    def calendars(self):
        with self.db.sessions() as s:
            return [record(c) for c in s.scalars(select(Calendar).where(~Calendar.deleted))]

    def _calendar(self, s, calendar_id, write=False):
        c = s.get(Calendar, calendar_id)
        if not c or c.deleted:
            raise DomainError("not_found", "Calendar not found", http_status=404)
        if write and not c.writable:
            raise DomainError("permission_denied", "Calendar is read-only", http_status=403)
        return c

    def _event(self, s, event_id):
        e = s.get(Event, event_id)
        if not e or e.deleted:
            raise DomainError("not_found", "Event not found", http_status=404)
        self._calendar(s, e.calendar_id)
        return e

    def events(self, start, end, query="", calendar_id=None):
        start, end = instant(start), instant(end)
        if start >= end or datetime.fromisoformat(end) - datetime.fromisoformat(start) > timedelta(
            days=93
        ):
            raise DomainError(
                "invalid_range", "Choose a positive range of at most 93 days", http_status=422
            )
        with self.db.sessions() as s:
            statement = (
                select(Event)
                .join(Calendar)
                .where(
                    ~Event.deleted,
                    ~Calendar.deleted,
                    Event.start < end,
                    Event.end > start,
                )
                .order_by(Event.start)
                .limit(200)
            )
            if calendar_id:
                self._calendar(s, calendar_id)
                statement = statement.where(Event.calendar_id == calendar_id)
            if query:
                statement = statement.where(Event.title.icontains(query, autoescape=True))
            return [record(e) for e in s.scalars(statement)]

    def get_event(self, event_id):
        with self.db.sessions() as s:
            return record(self._event(s, event_id))

    def _conflicts(self, s, fields, exclude=None):
        statement = (
            select(Event)
            .join(Calendar)
            .where(
                ~Event.deleted,
                ~Calendar.deleted,
                Event.busy,
                Event.start < fields["end"],
                Event.end > fields["start"],
            )
            .order_by(Event.start)
        )
        if exclude:
            statement = statement.where(Event.id != exclude)
        return [record(e) for e in s.scalars(statement)]

    def _check_target(self, s, payload):
        e = self._event(s, payload["event_id"])
        self._calendar(s, e.calendar_id, write=True)
        if e.version != payload["expected_version"]:
            raise DomainError("stale_version", "Event changed; review a fresh proposal")
        if e.recurring or e.all_day:
            raise DomainError("unsupported", "V1 only modifies single timed events")
        return e

    def propose(self, operation, payload):
        try:
            with self.db.sessions.begin() as s:
                self.db.lock(s)
                if self.source_job_id:
                    existing = s.scalar(
                        select(Proposal).where(Proposal.source_job_id == self.source_job_id)
                    )
                    if existing:
                        return record(existing)
                before, conflicts = None, []
                if operation == "event_create":
                    data = EventInput.model_validate(payload)
                    self._calendar(s, data.calendar_id, write=True)
                    payload = {"id": uid(), **data.event_fields()}
                    conflicts = self._conflicts(s, payload)
                elif operation == "event_update":
                    data = EventChange.model_validate(payload)
                    before = record(self._check_target(s, data.model_dump()))
                    if data.event.calendar_id != before["calendar_id"]:
                        raise DomainError(
                            "unsupported", "Moving between calendars is not supported"
                        )
                    payload = {
                        "event_id": data.event_id,
                        "expected_version": data.expected_version,
                        **data.event.event_fields(),
                    }
                    conflicts = self._conflicts(s, payload, data.event_id)
                elif operation == "event_delete":
                    data = EventDelete.model_validate(payload)
                    payload = data.model_dump()
                    before = record(self._check_target(s, payload))
                elif operation == "calendar_create":
                    payload = {"id": uid(), **CalendarInput.model_validate(payload).model_dump()}
                elif operation in {"calendar_update", "calendar_delete"}:
                    c = self._calendar(s, payload.get("calendar_id"), write=True)
                    if c.provider != "local":
                        raise DomainError(
                            "unsupported", "Provider calendar metadata is managed externally"
                        )
                    if c.version != payload.get("expected_version"):
                        raise DomainError("stale_version", "Calendar changed")
                    before = record(c)
                    base = {"calendar_id": c.id, "expected_version": c.version}
                    if operation == "calendar_delete":
                        if not c.app_created or c.id == "personal":
                            raise DomainError("permission_denied", "This calendar is protected")
                        base["affected_events"] = [
                            record(e)
                            for e in s.scalars(
                                select(Event).where(Event.calendar_id == c.id, ~Event.deleted)
                            )
                        ]
                    else:
                        base.update(
                            CalendarInput.model_validate(payload.get("calendar")).model_dump()
                        )
                    payload = base
                else:
                    raise DomainError("unknown_tool", "Unsupported operation", http_status=422)
                p = Proposal(
                    operation=operation,
                    payload=payload,
                    before=before,
                    result={"conflicts": conflicts},
                    source_job_id=self.source_job_id,
                )
                s.add(p)
                s.flush()
                return record(p)
        except ValidationError as e:
            raise DomainError(
                "needs_clarification",
                "Check required fields and values",
                e.errors(include_context=False),
                422,
            ) from e

    def proposal(self, proposal_id):
        with self.db.sessions() as s:
            p = s.get(Proposal, proposal_id)
            if not p:
                raise DomainError("not_found", "Proposal not found", http_status=404)
            return record(p)

    def proposals(self):
        with self.db.sessions() as s:
            return [
                record(p)
                for p in s.scalars(select(Proposal).order_by(Proposal.created_at.desc()).limit(50))
            ]

    def _validate_current(self, s, p, allow_overlap):
        fields = p.payload
        if p.operation in {"event_update", "event_delete"}:
            self._check_target(s, fields)
        if p.operation in {"event_create", "event_update"}:
            self._calendar(s, fields["calendar_id"], write=True)
            conflicts = self._conflicts(s, fields, fields.get("event_id"))
            if conflicts and not allow_overlap:
                raise DomainError("conflict", "This overlaps another event", conflicts)
        if p.operation in {"calendar_update", "calendar_delete"}:
            c = self._calendar(s, fields["calendar_id"], write=True)
            if c.version != fields["expected_version"]:
                raise DomainError("stale_version", "Calendar changed")
            if p.operation == "calendar_delete":
                current = [
                    record(e)
                    for e in s.scalars(
                        select(Event).where(Event.calendar_id == c.id, ~Event.deleted)
                    )
                ]
                if current != fields["affected_events"]:
                    raise DomainError(
                        "stale_version", "Calendar contents changed; review deletion again"
                    )

    def approve(self, proposal_id, allow_overlap=False):
        with self.db.sessions.begin() as s:
            self.db.lock(s)
            p = s.get(Proposal, proposal_id)
            if not p:
                raise DomainError("not_found", "Proposal not found", http_status=404)
            if p.status in {"queued", "syncing", "confirmed"}:
                return record(p)
            if p.status != "pending":
                raise DomainError("invalid_state", "This proposal cannot be accepted")
            self._validate_current(s, p, allow_overlap)
            p.status, p.allow_overlap = "queued", allow_overlap
            s.add(Job(request_key=f"execute:{p.id}", kind="execute", payload={"proposal_id": p.id}))
            s.flush()
            return record(p)

    def reject(self, proposal_id):
        with self.db.sessions.begin() as s:
            self.db.lock(s)
            p = s.get(Proposal, proposal_id)
            if not p:
                raise DomainError("not_found", "Proposal not found", http_status=404)
            if p.status != "pending":
                raise DomainError("invalid_state", "Only pending proposals can be rejected")
            p.status = "rejected"
            return record(p)

    def retry_execution(self, proposal_id):
        """Reconcile an uncertain provider write using the original approved operation ID."""
        with self.db.sessions.begin() as s:
            self.db.lock(s)
            p = s.get(Proposal, proposal_id)
            if not p:
                raise DomainError("not_found", "Proposal not found", http_status=404)
            if p.status != "uncertain":
                raise DomainError("invalid_state", "Only uncertain executions can be reconciled")
            j = s.scalar(select(Job).where(Job.request_key == f"execute:{p.id}"))
            j.status, j.attempts, j.error = "queued", 0, None
            p.status, p.error = "queued", None
            return record(p)

    def execute_local(self, proposal_id):
        with self.db.sessions.begin() as s:
            self.db.lock(s)
            p = s.get(Proposal, proposal_id)
            if p.status == "confirmed":
                return p.result
            if p.status not in {"queued", "syncing"}:
                raise DomainError("invalid_state", "Operation was not approved")
            self._validate_current(s, p, p.allow_overlap)
            f = p.payload
            if p.operation == "event_create":
                e = Event(**f)
                s.add(e)
            elif p.operation == "event_update":
                e = self._event(s, f["event_id"])
                for key, value in f.items():
                    if key not in {"event_id", "expected_version"}:
                        setattr(e, key, value)
                e.version += 1
            elif p.operation == "event_delete":
                e = self._event(s, f["event_id"])
                e.deleted, e.version = True, e.version + 1
            elif p.operation == "calendar_create":
                e = Calendar(**f)
                s.add(e)
            else:
                e = self._calendar(s, f["calendar_id"], write=True)
                if p.operation == "calendar_update":
                    e.name, e.timezone = f["name"], f["timezone"]
                else:
                    e.deleted = True
                    for item in s.scalars(select(Event).where(Event.calendar_id == e.id)):
                        item.deleted, item.version = True, item.version + 1
                e.version += 1
            s.flush()
            result = record(e)
            s.add(Audit(proposal_id=p.id, before=p.before, after=result))
            p.status, p.result, p.error = "confirmed", result, None
            return result
