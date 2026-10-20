import asyncio
import time
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import or_, select

from jarvis.agent import Agent, LocalLLM, MCPTools
from jarvis.audio import Transcriber
from jarvis.calendar import CalendarService, DomainError
from jarvis.config import Settings
from jarvis.db import Calendar, Conversation, Database, Job, Proposal, now, record
from jarvis.google import GoogleCalendar
from jarvis.tools import InProcessTools, ToolRegistry


class Worker:
    def __init__(self, settings, db, agent=None, transcriber=None, google=None):
        self.settings, self.db = settings, db
        self.service = CalendarService(db)
        tools = (
            MCPTools(settings)
            if settings.mcp_transport == "stdio"
            else InProcessTools(ToolRegistry(self.service))
        )
        self.agent = agent or Agent(LocalLLM(settings), tools)
        self.transcriber = transcriber or Transcriber(settings)
        self.google = google or GoogleCalendar(settings, db, self.service)

    def claim(self):
        with self.db.sessions.begin() as s:
            self.db.lock(s)
            job = s.scalar(
                select(Job)
                .where(
                    or_(
                        Job.status == "queued",
                        (Job.status == "running") & (Job.lease_until < now()),
                    )
                )
                .order_by(Job.created_at)
                .limit(1)
            )
            if not job:
                return None
            if job.attempts >= 4:
                job.status, job.error = (
                    "failed",
                    "Retry limit reached; review the pending operation",
                )
                if job.kind == "execute":
                    p = s.get(Proposal, job.payload["proposal_id"])
                    p.status, p.error = "uncertain", job.error
                return None
            job.status, job.attempts = "running", job.attempts + 1
            job.lease_until = (datetime.now(UTC) + timedelta(minutes=30)).isoformat()
            return record(job)

    def execute(self, proposal_id):
        p = self.service.proposal(proposal_id)
        if p["status"] == "confirmed":
            return p["result"]
        calendar_id = p["payload"].get("calendar_id") or (p["before"] or {}).get("calendar_id")
        with self.db.sessions() as s:
            c = s.get(Calendar, calendar_id) if calendar_id else None
            provider = c.provider if c else "local"
        if provider == "google":
            return self.google.execute(proposal_id)
        return self.service.execute_local(proposal_id)

    def step(self):
        job = self.claim()
        if not job:
            return False
        new_history = None
        try:
            if job["kind"] == "execute":
                result = self.execute(job["payload"]["proposal_id"])
            elif job["kind"] == "sync":
                result = self.google.sync()
            else:
                with self.db.sessions() as s:
                    c = s.get(Conversation, job["conversation_id"])
                    history, capture, tz = c.messages, c.captured_at, c.timezone
                text = job["payload"].get("text")
                if job["kind"] == "audio" and not text:
                    source = self.settings.data_dir / "audio" / job["payload"]["filename"]
                    text = self.transcriber.transcribe(source)
                    # Persist transcript before unlinking so interrupted processing is recoverable.
                    with self.db.sessions.begin() as s:
                        j = s.get(Job, job["id"])
                        j.payload = {**j.payload, "text": text}
                    source.unlink(missing_ok=True)
                self.service.source_job_id = job["id"]
                if hasattr(self.agent, "tools"):
                    self.agent.tools.source_job_id = job["id"]
                result = asyncio.run(self.agent.run(history, text, capture, tz))
                new_history = result.pop("history")
                result = {**result, "transcript": text, "conversation_id": job["conversation_id"]}
            with self.db.sessions.begin() as s:
                j = s.get(Job, job["id"])
                j.status, j.result, j.error = "completed", result, None
                if new_history is not None:
                    c = s.get(Conversation, job["conversation_id"])
                    c.messages, c.version = new_history, c.version + 1
        except Exception as e:
            transient = isinstance(e, (httpx.TransportError, httpx.HTTPStatusError)) and (
                not isinstance(e, httpx.HTTPStatusError)
                or e.response.status_code >= 500
                or e.response.status_code == 429
            )
            # Retry uncertain provider writes with stable operation IDs, never a new create ID.
            retry = transient and job["kind"] in {"execute", "sync"} and job["attempts"] < 4
            message = (
                e.message
                if isinstance(e, DomainError)
                else (
                    str(e)
                    if isinstance(e, ValueError)
                    else "Processing failed. Check local services and retry."
                )
            )
            with self.db.sessions.begin() as s:
                j = s.get(Job, job["id"])
                j.status, j.error = ("running" if retry else "failed"), message[:1000]
                j.lease_until = (
                    datetime.now(UTC) + timedelta(seconds=2 ** job["attempts"])
                ).isoformat()
                if job["kind"] == "execute":
                    p = s.get(Proposal, job["payload"]["proposal_id"])
                    p.status = (
                        "syncing"
                        if retry
                        else (
                            "uncertain"
                            if transient
                            else ("conflict" if isinstance(e, DomainError) else "failed")
                        )
                    )
                    p.error = message[:1000]
        self.cleanup()
        return True

    def cleanup(self):
        cutoff = time.time() - 24 * 60 * 60
        for path in (self.settings.data_dir / "audio").iterdir():
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)


def main():
    settings = Settings()
    db = Database(settings)
    db.initialize(settings.timezone)
    worker = Worker(settings, db)
    while True:
        if not worker.step():
            worker.cleanup()
            time.sleep(1)


if __name__ == "__main__":
    main()
