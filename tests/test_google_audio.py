import json
import subprocess
import wave
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from jarvis.audio import Transcriber
from jarvis.calendar import DomainError
from jarvis.db import Calendar, Event
from jarvis.google import GoogleCalendar
from sqlalchemy import select


@pytest.fixture
def google(settings, db, service):
    (settings.data_dir / "google-calendar.json").write_text(json.dumps({"calendar_id": "primary"}))
    return GoogleCalendar(settings, db, service)


def remote_event(event_id="remote1", etag='"v1"', **changes):
    start = (datetime.now(UTC) + timedelta(days=1)).replace(
        hour=11, minute=0, second=0, microsecond=0
    )
    return {
        "id": event_id,
        "etag": etag,
        "summary": "Dinner",
        "location": "Home",
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": (start + timedelta(hours=1)).isoformat()},
        **changes,
    }


def setup_google_client(google, handler):
    def route(request):
        path = request.url.path
        if path.endswith("/calendarList/primary"):
            return httpx.Response(200, json={"accessRole": "owner"})
        if path.endswith("/calendars/primary"):
            return httpx.Response(
                200,
                json={"id": "test@example.com", "summary": "Test", "timeZone": "Asia/Singapore"},
            )
        return handler(request)

    google.client = lambda: httpx.Client(
        base_url="https://provider.test", transport=httpx.MockTransport(route)
    )


def test_sync_reconciles_phone_edits_and_removed_busy_blocks(google, db, service):
    items = [remote_event()]
    setup_google_client(google, lambda _: httpx.Response(200, json={"items": items}))
    result = google.sync()
    with db.sessions() as s:
        original = s.scalar(select(Event))
        event_id = original.id
        assert original.title == "Dinner"
    items[0] = remote_event(etag='"v2"', summary="Changed on phone")
    google.sync()
    assert service.get_event(event_id)["version"] == 2
    assert service.get_event(event_id)["title"] == "Changed on phone"
    items.clear()
    google.sync()
    with db.sessions() as s:
        assert s.get(Event, event_id).deleted
        assert not s.get(Calendar, result["calendar"]["id"]).app_created


def test_all_day_and_recurring_entries_are_busy_but_not_writable(google, service, db):
    date = (datetime.now(UTC) + timedelta(days=1)).date()
    items = [
        remote_event(
            start={"date": date.isoformat()},
            end={"date": (date + timedelta(days=1)).isoformat()},
            recurringEventId="series",
        )
    ]
    setup_google_client(google, lambda _: httpx.Response(200, json={"items": items}))
    google.sync()
    with db.sessions() as s:
        e = s.scalar(select(Event))
        assert e.all_day and e.recurring and e.busy
        assert datetime.fromisoformat(e.start).hour == 16  # Singapore midnight in UTC
        event_id = e.id
    with pytest.raises(DomainError, match="single timed"):
        service.propose("event_delete", {"event_id": event_id, "expected_version": 1})


def test_google_create_timeout_reconciles_same_id_without_duplicate(
    google, service, event_data, db
):
    with db.sessions.begin() as s:
        s.add(
            Calendar(id="google", name="Google", provider="google", provider_id="test@example.com")
        )
    p = service.propose("event_create", {**event_data, "calendar_id": "google"})
    service.approve(p["id"])
    remote, writes = {}, []
    google.sync = lambda **kwargs: None

    def handler(request):
        if request.method == "GET":
            found = remote.get(request.url.path.rsplit("/", 1)[-1])
            return httpx.Response(200, json=found) if found else httpx.Response(404)
        body = json.loads(request.content)
        writes.append(body)
        item = {**body, "etag": '"created"'}
        remote[body["id"]] = item
        raise httpx.ReadTimeout("response lost", request=request)

    setup_google_client(google, handler)
    with pytest.raises(httpx.ReadTimeout):
        google.execute(p["id"])
    result = google.execute(p["id"])
    assert result["provider_id"] == p["payload"]["id"]
    assert len(writes) == 1
    assert service.proposal(p["id"])["status"] == "confirmed"


def test_google_update_uses_if_match_and_only_minimal_fields(google, service, db):
    item = remote_event()
    with db.sessions.begin() as s:
        s.add(
            Calendar(id="google", name="Google", provider="google", provider_id="test@example.com")
        )
        s.flush()
        e = Event(
            id="local",
            calendar_id="google",
            provider_id=item["id"],
            **google.fields(item, "Asia/Singapore"),
        )
        s.add(e)
    local_start = datetime.fromisoformat(item["start"]["dateTime"]).astimezone(
        __import__("zoneinfo").ZoneInfo("Asia/Singapore")
    )
    p = service.propose(
        "event_update",
        {
            "event_id": "local",
            "expected_version": 1,
            "event": {
                "calendar_id": "google",
                "title": "New title",
                "start": local_start.isoformat(),
                "duration_minutes": 60,
                "timezone": "Asia/Singapore",
                "location": "Home",
            },
        },
    )
    service.approve(p["id"])
    google.sync = lambda **kwargs: None
    seen = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=item)
        seen.append(request)
        assert request.headers["If-Match"] == '"v1"'
        body = json.loads(request.content)
        assert set(body) == {"summary", "location", "start", "end"}
        return httpx.Response(200, json={**item, **body, "etag": '"v2"'})

    setup_google_client(google, handler)
    assert google.execute(p["id"])["title"] == "New title"
    assert len(seen) == 1


def test_google_precondition_failure_is_a_conflict(google):
    with pytest.raises(DomainError) as error:
        google._data(httpx.Response(412))
    assert error.value.code == "stale_version"


def test_google_oauth_not_silently_used_when_unconfigured(google):
    with pytest.raises(DomainError, match="OAuth"):
        google.client()


def test_transcription_normalizes_audio_and_removes_intermediates(settings, monkeypatch):
    source = settings.data_dir / "audio" / "clip.upload"
    source.write_bytes(b"uploaded")
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[0] == settings.ffmpeg_bin:
            with wave.open(args[-1], "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(16000)
                audio.writeframes(b"\xff\x03" * 16000)
        else:
            path = Path(args[args.index("-of") + 1] + ".json")
            path.write_text(json.dumps({"transcription": [{"text": " Dinner tomorrow "}]}))

    monkeypatch.setattr(subprocess, "run", run)
    assert Transcriber(settings).transcribe(source) == "Dinner tomorrow"
    assert calls[0][calls[0].index("-ar") + 1] == "16000"
    assert source.exists()  # worker deletes only after transcript is durable
    assert list(source.parent.iterdir()) == [source]


def test_silence_never_reaches_language_model(settings, monkeypatch):
    source = settings.data_dir / "audio" / "silence.upload"
    source.write_bytes(b"uploaded")

    def run(args, **kwargs):
        with wave.open(args[-1], "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\0\0" * 16000)

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(ValueError, match="No speech"):
        Transcriber(settings).transcribe(source)
