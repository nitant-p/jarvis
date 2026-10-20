"""Selected Google calendar adapter. OAuth is explicit; credentials never enter model context."""

import json
import os
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sqlalchemy import select

from jarvis.calendar import DomainError
from jarvis.db import Audit, Calendar, Event, Proposal, record

SCOPE = "https://www.googleapis.com/auth/calendar"
ROOT = "https://www.googleapis.com/calendar/v3"


def write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(data)


class GoogleCalendar:
    def __init__(self, settings, db, service):
        self.settings, self.db, self.service = settings, db, service
        self.token_path = settings.data_dir / "google-token.json"
        self.config_path = settings.data_dir / "google-calendar.json"

    def client(self):
        if not self.token_path.exists():
            raise DomainError(
                "not_connected", "Run the Google OAuth setup command first", http_status=503
            )
        credentials = Credentials.from_authorized_user_file(str(self.token_path), [SCOPE])
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            write_private(self.token_path, credentials.to_json())
        if not credentials.valid:
            raise DomainError("not_connected", "Reconnect Google Calendar", http_status=503)
        return httpx.Client(
            base_url=ROOT, headers={"Authorization": f"Bearer {credentials.token}"}, timeout=30
        )

    def _data(self, response):
        if response.status_code in {401, 403}:
            raise DomainError(
                "permission_denied", "Google authorization or permissions need review"
            )
        if response.status_code == 412:
            raise DomainError("stale_version", "Google event changed since the proposal")
        response.raise_for_status()
        return response.json() if response.content else {}

    @staticmethod
    def fields(item, timezone):
        all_day = "date" in item.get("start", {})
        tz = ZoneInfo(timezone)

        def parse(value):
            dt = datetime.fromisoformat(value.get("dateTime") or value["date"])
            if dt.utcoffset() is None:
                dt = dt.replace(tzinfo=tz)
            return dt.astimezone(UTC).isoformat()

        return {
            "title": item.get("summary") or "Untitled",
            "start": parse(item["start"]),
            "end": parse(item["end"]),
            "timezone": timezone,
            "location": item.get("location", ""),
            "all_day": all_day,
            "recurring": bool(item.get("recurringEventId") or item.get("recurrence")),
            "busy": item.get("transparency") != "transparent",
            "etag": item.get("etag"),
        }

    def sync(self, start=None, end=None):
        if not self.config_path.exists():
            raise DomainError("not_connected", "No Google calendar selected", http_status=503)
        selected = json.loads(self.config_path.read_text())["calendar_id"]
        start = start or (datetime.now(UTC) - timedelta(days=31)).isoformat()
        end = end or (datetime.now(UTC) + timedelta(days=93)).isoformat()
        with self.client() as client:
            metadata = self._data(client.get(f"/calendars/{selected}"))
            access = self._data(client.get(f"/users/me/calendarList/{selected}"))
            canonical_id = metadata["id"]
            items, page = [], None
            while True:
                params = {
                    "timeMin": start,
                    "timeMax": end,
                    "singleEvents": "true",
                    "showDeleted": "true",
                    "maxResults": 2500,
                }
                if page:
                    params["pageToken"] = page
                batch = self._data(client.get(f"/calendars/{canonical_id}/events", params=params))
                items.extend(batch.get("items", []))
                page = batch.get("nextPageToken")
                if not page:
                    break
        timezone = metadata.get("timeZone", self.settings.timezone)
        with self.db.sessions.begin() as s:
            self.db.lock(s)
            c = s.scalar(
                select(Calendar).where(
                    Calendar.provider == "google", Calendar.provider_id == canonical_id
                )
            )
            if not c:
                c = Calendar(
                    name=metadata.get("summary", "Google"),
                    timezone=timezone,
                    provider="google",
                    provider_id=canonical_id,
                    app_created=False,
                )
                s.add(c)
                s.flush()
            c.writable = access.get("accessRole") in {"owner", "writer"}
            seen = set()
            for item in items:
                seen.add(item["id"])
                e = s.scalar(
                    select(Event).where(Event.calendar_id == c.id, Event.provider_id == item["id"])
                )
                if item.get("status") == "cancelled":
                    if e and not e.deleted:
                        e.deleted, e.version = True, e.version + 1
                    continue
                fields = self.fields(item, timezone)
                if not e:
                    s.add(Event(calendar_id=c.id, provider_id=item["id"], **fields))
                elif e.etag != fields["etag"] or e.deleted:
                    for key, value in fields.items():
                        setattr(e, key, value)
                    e.version, e.deleted = e.version + 1, False
            # Remove moved-away events so they do not remain phantom busy blocks.
            for e in s.scalars(
                select(Event).where(
                    Event.calendar_id == c.id, ~Event.deleted, Event.start < end, Event.end > start
                )
            ):
                if e.provider_id not in seen:
                    e.deleted, e.version = True, e.version + 1
            s.flush()
            return {
                "calendar": record(c),
                "events_received": len(items),
                "start": start,
                "end": end,
            }

    def execute(self, proposal_id):
        # Refresh the actual requested window, including dates outside the default UI horizon.
        preview = self.service.proposal(proposal_id)
        target = preview["payload"] if "start" in preview["payload"] else preview["before"]
        self.sync(start=target["start"], end=target["end"])
        with self.db.sessions() as s:
            p = s.get(Proposal, proposal_id)
            if p.status == "confirmed":
                return p.result
            if p.status not in {"queued", "syncing"}:
                raise DomainError("invalid_state", "Operation was not approved")
            f, before = p.payload, p.before
            c = self.service._calendar(s, f.get("calendar_id") or before["calendar_id"], write=True)
            remote_calendar = c.provider_id
            remote_id = f.get("id") if p.operation == "event_create" else before["provider_id"]
            operation = p.operation
            # Reconcile first: the previous write may have succeeded before a timeout.
        with self.client() as client:
            path = f"/calendars/{remote_calendar}/events/{remote_id}"
            response = client.get(path)
            existing = None if response.status_code in {404, 410} else self._data(response)
            if operation == "event_delete" and existing is None:
                result = None
            else:
                body = {
                    "summary": f.get("title"),
                    "location": f.get("location", ""),
                    "start": {"dateTime": f.get("start"), "timeZone": f.get("timezone")},
                    "end": {"dateTime": f.get("end"), "timeZone": f.get("timezone")},
                }
                same = (
                    existing
                    and operation != "event_delete"
                    and all(
                        self.fields(existing, f["timezone"])[key] == f[key]
                        for key in ("title", "start", "end", "location")
                    )
                )
                if same:
                    result = existing
                else:
                    with self.db.sessions() as s:
                        p = s.get(Proposal, proposal_id)
                        self.service._validate_current(s, p, p.allow_overlap)
                    if operation == "event_create":
                        if existing:
                            raise DomainError(
                                "conflict", "Provider event ID already exists with different data"
                            )
                        result = self._data(
                            client.post(
                                f"/calendars/{remote_calendar}/events",
                                json={"id": remote_id, **body},
                                params={"sendUpdates": "none"},
                            )
                        )
                    elif operation == "event_update":
                        result = self._data(
                            client.patch(
                                path,
                                json=body,
                                headers={"If-Match": before["etag"]},
                                params={"sendUpdates": "none"},
                            )
                        )
                    else:
                        self._data(
                            client.delete(
                                path,
                                headers={"If-Match": before["etag"]},
                                params={"sendUpdates": "none"},
                            )
                        )
                        result = None
        with self.db.sessions.begin() as s:
            self.db.lock(s)
            p = s.get(Proposal, proposal_id)
            e = s.scalar(
                select(Event).where(Event.calendar_id == c.id, Event.provider_id == remote_id)
            )
            if result is None:
                if e:
                    e.deleted, e.version = True, e.version + 1
                after = {"provider_id": remote_id, "deleted": True}
            else:
                fields = self.fields(result, c.timezone)
                if not e:
                    e = Event(id=f.get("id"), calendar_id=c.id, provider_id=remote_id, **fields)
                    s.add(e)
                else:
                    for key, value in fields.items():
                        setattr(e, key, value)
                    e.deleted, e.version = False, e.version + 1
                s.flush()
                after = record(e)
            if not s.scalar(select(Audit).where(Audit.proposal_id == p.id)):
                s.add(Audit(proposal_id=p.id, before=p.before, after=after))
            p.status, p.result, p.error = "confirmed", after, None
            return after


def authorize():
    import argparse

    from google_auth_oauthlib.flow import InstalledAppFlow

    from jarvis.config import Settings

    parser = argparse.ArgumentParser(description="Connect one Google calendar explicitly")
    parser.add_argument("--client-secrets", required=True)
    parser.add_argument("--calendar-id", default="primary")
    args = parser.parse_args()
    settings = Settings()
    settings.prepare()
    flow = InstalledAppFlow.from_client_secrets_file(args.client_secrets, [SCOPE])
    credentials = flow.run_local_server(port=0)
    write_private(settings.data_dir / "google-token.json", credentials.to_json())
    write_private(
        settings.data_dir / "google-calendar.json", json.dumps({"calendar_id": args.calendar_id})
    )
    print("Google credentials saved privately. Use Sync Google in Jarvis to import this calendar.")


if __name__ == "__main__":
    authorize()
