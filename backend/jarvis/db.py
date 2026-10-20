import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def uid() -> str:
    return uuid4().hex


def now() -> str:
    return datetime.now(UTC).isoformat()


class Base(DeclarativeBase):
    pass


class Calendar(Base):
    __tablename__ = "calendars"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    name: Mapped[str]
    timezone: Mapped[str] = mapped_column(default="Asia/Singapore")
    provider: Mapped[str] = mapped_column(default="local")
    provider_id: Mapped[str | None]
    writable: Mapped[bool] = mapped_column(Boolean, default=True)
    app_created: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(default=1)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    calendar_id: Mapped[str] = mapped_column(ForeignKey("calendars.id"), index=True)
    title: Mapped[str]
    start: Mapped[str] = mapped_column(index=True)
    end: Mapped[str]
    timezone: Mapped[str]
    location: Mapped[str] = mapped_column(default="")
    duration_is_estimate: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(default=1)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    provider_id: Mapped[str | None]
    etag: Mapped[str | None]
    recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    busy: Mapped[bool] = mapped_column(Boolean, default=True)


class Proposal(Base):
    __tablename__ = "proposals"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    operation: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    before: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(default="pending")
    allow_overlap: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(default=now)
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None]
    source_job_id: Mapped[str | None] = mapped_column(String, unique=True, index=True)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    captured_at: Mapped[str] = mapped_column(default=now)
    timezone: Mapped[str]
    messages: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(default=1)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    request_key: Mapped[str] = mapped_column(String, unique=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"), index=True)
    kind: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(default="queued", index=True)
    created_at: Mapped[str] = mapped_column(default=now)
    lease_until: Mapped[str | None]
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), unique=True)
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(default=now)


def record(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


class Database:
    def __init__(self, settings):
        settings.prepare()
        self.engine = create_engine(settings.db_url, connect_args={"timeout": 10})

        @event.listens_for(self.engine, "connect")
        def configure(dbapi_connection, _):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")
            dbapi_connection.execute("PRAGMA journal_mode=WAL")

        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def initialize(self, timezone="Asia/Singapore"):
        Base.metadata.create_all(self.engine)
        with self.sessions.begin() as s:
            if not s.get(Calendar, "personal"):
                s.add(Calendar(id="personal", name="Personal", timezone=timezone))

    def lock(self, s):
        # Serialize state transitions across API, worker, and MCP subprocesses.
        from sqlalchemy import text

        s.execute(text("BEGIN IMMEDIATE"))


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
