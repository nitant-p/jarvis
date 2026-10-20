from concurrent.futures import ThreadPoolExecutor

import pytest
from jarvis.calendar import DomainError
from jarvis.db import Audit, Calendar, Event, Job
from sqlalchemy import func, select


def test_no_event_before_approval_and_execution(service, event_data, db):
    p = service.propose("event_create", event_data)
    with db.sessions() as s:
        assert s.scalar(select(func.count()).select_from(Event)) == 0
    with pytest.raises(DomainError, match="not approved"):
        service.execute_local(p["id"])
    service.approve(p["id"])
    result = service.execute_local(p["id"])
    assert result["title"] == event_data["title"]
    assert result["start"] == "2026-10-21T11:00:00+00:00"
    assert result["end"] == "2026-10-21T12:00:00+00:00"


def test_duplicate_approval_and_execution_are_idempotent(service, event_data, db):
    p = service.propose("event_create", event_data)
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda _: service.approve(p["id"]), range(4)))
    first = service.execute_local(p["id"])
    assert service.execute_local(p["id"]) == first
    with db.sessions() as s:
        assert s.scalar(select(func.count()).select_from(Event)) == 1
        assert s.scalar(select(func.count()).select_from(Job)) == 1
        assert s.scalar(select(func.count()).select_from(Audit)) == 1


def test_update_and_delete_preserve_audit(service, create_event, event_data, db):
    event = create_event()
    p = service.propose(
        "event_update",
        {
            "event_id": event["id"],
            "expected_version": 1,
            "event": {**event_data, "start": "2026-10-21T20:00:00+08:00"},
        },
    )
    service.approve(p["id"])
    updated = service.execute_local(p["id"])
    assert updated["version"] == 2
    assert updated["location"] == "Home"
    p = service.propose("event_delete", {"event_id": event["id"], "expected_version": 2})
    service.approve(p["id"])
    assert service.execute_local(p["id"])["deleted"]
    with pytest.raises(DomainError, match="not found"):
        service.get_event(event["id"])
    with db.sessions() as s:
        assert s.scalar(select(func.count()).select_from(Audit)) == 3


def test_adjacent_events_allowed_overlaps_require_explicit_acceptance(
    service, create_event, event_data
):
    create_event()
    adjacent = service.propose("event_create", {**event_data, "start": "2026-10-21T20:00:00+08:00"})
    assert adjacent["result"]["conflicts"] == []
    overlapping = service.propose("event_create", event_data)
    assert len(overlapping["result"]["conflicts"]) == 1
    with pytest.raises(DomainError) as error:
        service.approve(overlapping["id"])
    assert error.value.code == "conflict"
    service.approve(overlapping["id"], allow_overlap=True)
    service.execute_local(overlapping["id"])


def test_conflict_added_after_approval_is_rechecked(service, create_event, event_data):
    proposed = service.propose("event_create", event_data)
    service.approve(proposed["id"])
    create_event()
    with pytest.raises(DomainError) as error:
        service.execute_local(proposed["id"])
    assert error.value.code == "conflict"


def test_stale_event_previews_cannot_overwrite_edits(service, create_event, event_data):
    event = create_event()
    stale = service.propose("event_delete", {"event_id": event["id"], "expected_version": 1})
    change = service.propose(
        "event_update",
        {
            "event_id": event["id"],
            "expected_version": 1,
            "event": {**event_data, "title": "New dinner title"},
        },
    )
    service.approve(change["id"])
    service.execute_local(change["id"])
    with pytest.raises(DomainError) as error:
        service.approve(stale["id"])
    assert error.value.code == "stale_version"
    assert service.get_event(event["id"])["title"] == "New dinner title"


@pytest.mark.parametrize(
    "changes",
    [
        {"duration_minutes": 0},
        {"duration_minutes": -1},
        {"timezone": "Mars"},
        {"start": "2026-10-21T19:00:00"},
        {"start": "2026-10-21T19:00:00+00:00"},
        {"title": "  "},
        {"untrusted_extra": "anything"},
    ],
)
def test_invalid_events_never_become_proposals(service, event_data, changes):
    with pytest.raises(DomainError) as error:
        service.propose("event_create", {**event_data, **changes})
    assert error.value.code == "needs_clarification"
    assert not service.proposals()


def test_dst_nonexistent_wall_time_rejected_but_explicit_folds_accepted(service, event_data):
    with pytest.raises(DomainError):
        service.propose(
            "event_create",
            {**event_data, "timezone": "America/New_York", "start": "2026-03-08T02:30:00-05:00"},
        )
    for offset in ["-04:00", "-05:00"]:
        p = service.propose(
            "event_create",
            {**event_data, "timezone": "America/New_York", "start": f"2026-11-01T01:30:00{offset}"},
        )
        assert p["status"] == "pending"


def test_conflicts_include_other_calendars_but_not_free_events(
    service, create_event, event_data, db
):
    with db.sessions.begin() as s:
        s.add(Calendar(id="work", name="Work"))
    event = create_event(calendar_id="work")
    assert service.propose("event_create", event_data)["result"]["conflicts"]
    with db.sessions.begin() as s:
        s.get(Event, event["id"]).busy = False
    assert not service.propose("event_create", event_data)["result"]["conflicts"]


def test_calendar_crud_and_deletion_previews_cannot_go_stale(service, event_data, db):
    p = service.propose("calendar_create", {"name": "Hobbies", "timezone": "Asia/Singapore"})
    service.approve(p["id"])
    calendar = service.execute_local(p["id"])
    deletion = service.propose(
        "calendar_delete", {"calendar_id": calendar["id"], "expected_version": 1}
    )
    p = service.propose("event_create", {**event_data, "calendar_id": calendar["id"]})
    service.approve(p["id"])
    service.execute_local(p["id"])
    with pytest.raises(DomainError, match="contents changed"):
        service.approve(deletion["id"])
    deletion = service.propose(
        "calendar_delete", {"calendar_id": calendar["id"], "expected_version": 1}
    )
    assert len(deletion["payload"]["affected_events"]) == 1
    service.approve(deletion["id"])
    service.execute_local(deletion["id"])
    assert calendar["id"] not in [c["id"] for c in service.calendars()]
    with db.sessions() as s:
        assert s.scalar(select(Event).where(Event.calendar_id == calendar["id"])).deleted


def test_protected_calendar_and_read_only_or_recurring_events(service, create_event, db):
    with pytest.raises(DomainError):
        service.propose("calendar_delete", {"calendar_id": "personal", "expected_version": 1})
    event = create_event()
    with db.sessions.begin() as s:
        s.get(Event, event["id"]).recurring = True
    with pytest.raises(DomainError, match="single timed"):
        service.propose("event_delete", {"event_id": event["id"], "expected_version": 1})
    with db.sessions.begin() as s:
        s.get(Event, event["id"]).recurring = False
        s.get(Calendar, "personal").writable = False
    with pytest.raises(DomainError) as error:
        service.propose("event_delete", {"event_id": event["id"], "expected_version": 1})
    assert error.value.code == "permission_denied"


def test_bounded_search_and_literal_title_filter(service, create_event):
    create_event(title="100% Dinner")
    assert len(service.events("2026-10-21T00:00:00+08:00", "2026-10-22T00:00:00+08:00", "%")) == 1
    assert not service.events("2026-10-21T00:00:00+08:00", "2026-10-22T00:00:00+08:00", "_")
    with pytest.raises(DomainError):
        service.events("2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z")
