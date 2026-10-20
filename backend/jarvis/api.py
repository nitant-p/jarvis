import hashlib
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy import select

from jarvis.calendar import CalendarService, DomainError
from jarvis.config import Settings
from jarvis.db import Conversation, Database, Job, canonical, record, uid
from jarvis.schemas import Approval, MessageInput, ProposalRequest


def create_app(settings=None, database=None):
    settings = settings or Settings()
    db = database or Database(settings)
    service = CalendarService(db)

    @asynccontextmanager
    async def lifespan(app):
        db.initialize(settings.timezone)
        yield

    app = FastAPI(
        title="Jarvis",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.db, app.state.settings = db, settings
    bearer = HTTPBearer(auto_error=False)

    def authenticate(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if len(settings.token) < 16:
            raise DomainError(
                "not_configured",
                "Set JARVIS_TOKEN to at least 16 random characters",
                http_status=503,
            )
        if not credentials or not secrets.compare_digest(credentials.credentials, settings.token):
            raise DomainError("unauthorized", "A valid access token is required", http_status=401)

    @app.exception_handler(DomainError)
    async def domain_error(request, error):
        return JSONResponse(error.as_dict(), status_code=error.http_status)

    @app.exception_handler(ValidationError)
    async def validation_error(request, error):
        return JSONResponse({"detail": error.errors(include_context=False)}, status_code=422)

    @app.middleware("http")
    async def headers(request, call_next):
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
            from urllib.parse import urlsplit

            if urlsplit(origin).netloc != request.headers.get("host"):
                return JSONResponse(
                    {"message": "Cross-origin writes are disabled"}, status_code=403
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        return response

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": "0.1.0"}

    protected = [Depends(authenticate)]

    @app.get("/api/settings", dependencies=protected)
    def public_settings():
        return {
            "timezone": settings.timezone,
            "model": settings.llm_model,
            "google_connected": (settings.data_dir / "google-token.json").exists(),
        }

    @app.get("/api/calendars", dependencies=protected)
    def calendars():
        return service.calendars()

    @app.get("/api/events", dependencies=protected)
    def events(start: str, end: str, query: str = "", calendar_id: str | None = None):
        return service.events(start, end, query, calendar_id)

    @app.get("/api/events/{event_id}", dependencies=protected)
    def get_event(event_id: str):
        return service.get_event(event_id)

    @app.post("/api/proposals", dependencies=protected, status_code=201)
    def propose(data: ProposalRequest):
        return service.propose(data.operation, data.payload)

    @app.get("/api/proposals", dependencies=protected)
    def proposals():
        return service.proposals()

    @app.get("/api/proposals/{proposal_id}", dependencies=protected)
    def proposal(proposal_id: str):
        return service.proposal(proposal_id)

    @app.post("/api/proposals/{proposal_id}/approve", dependencies=protected)
    def approve(proposal_id: str, data: Approval):
        return service.approve(proposal_id, data.allow_overlap)

    @app.post("/api/proposals/{proposal_id}/reject", dependencies=protected)
    def reject(proposal_id: str):
        return service.reject(proposal_id)

    @app.post("/api/proposals/{proposal_id}/retry", dependencies=protected)
    def retry_proposal(proposal_id: str):
        return service.retry_execution(proposal_id)

    def enqueue(request_key, kind, payload, conversation_id=None, capture=None, timezone=None):
        with db.sessions.begin() as s:
            db.lock(s)
            existing = s.scalar(select(Job).where(Job.request_key == request_key))
            if existing:
                # A retry may reuse the same key only for the same input.
                original = {
                    k: v for k, v in existing.payload.items() if k != "text" or kind == "text"
                }
                compare = {k: v for k, v in payload.items() if k != "filename"}
                original = {k: v for k, v in original.items() if k != "filename"}
                if existing.kind != kind or canonical(original) != canonical(compare):
                    raise DomainError(
                        "idempotency_conflict", "Request ID already used for a different input"
                    )
                return record(existing)
            if conversation_id:
                c = s.get(Conversation, conversation_id)
                if not c:
                    raise DomainError("not_found", "Conversation not found", http_status=404)
                if s.scalar(
                    select(Job).where(
                        Job.conversation_id == c.id, Job.status.in_(["queued", "running"])
                    )
                ):
                    raise DomainError("busy", "Wait for the current conversation turn to finish")
            elif kind in {"text", "audio"}:
                c = Conversation(
                    captured_at=capture or datetime.now(UTC).isoformat(),
                    timezone=timezone or settings.timezone,
                )
                s.add(c)
                s.flush()
                conversation_id = c.id
            j = Job(
                request_key=request_key, kind=kind, payload=payload, conversation_id=conversation_id
            )
            s.add(j)
            s.flush()
            return record(j)

    @app.post("/api/messages", dependencies=protected, status_code=202)
    def message(data: MessageInput):
        return enqueue(
            data.request_id,
            "text",
            {"text": data.text},
            data.conversation_id,
            data.captured_at.isoformat() if data.captured_at else None,
            data.timezone,
        )

    @app.post("/api/recordings", dependencies=protected, status_code=202)
    async def recording(
        audio: UploadFile = File(),
        request_id: str = Form(),
        conversation_id: str | None = Form(None),
        captured_at: str | None = Form(None),
        timezone: str = Form("Asia/Singapore"),
    ):
        # Reuse message metadata validation; filename/codec are never trusted commands.
        metadata = MessageInput(
            text="audio",
            request_id=request_id,
            conversation_id=conversation_id,
            captured_at=captured_at,
            timezone=timezone,
        )
        filename = uid() + ".upload"
        path = settings.data_dir / "audio" / filename
        digest, total = hashlib.sha256(), 0
        try:
            with path.open("wb") as output:
                path.chmod(0o600)
                while chunk := await audio.read(65536):
                    total += len(chunk)
                    if total > settings.max_upload_bytes:
                        raise DomainError(
                            "too_large", "Recording exceeds upload limit", http_status=413
                        )
                    digest.update(chunk)
                    output.write(chunk)
            if total == 0:
                raise DomainError("empty_audio", "Recording is empty", http_status=422)
            result = enqueue(
                request_id,
                "audio",
                {"filename": filename, "sha256": digest.hexdigest()},
                conversation_id,
                metadata.captured_at.isoformat() if metadata.captured_at else None,
                timezone,
            )
            if result["payload"]["filename"] != filename:
                path.unlink(missing_ok=True)
            return result
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:
            await audio.close()

    @app.get("/api/jobs/{job_id}", dependencies=protected)
    def job(job_id: str):
        with db.sessions() as s:
            j = s.get(Job, job_id)
            if not j:
                raise DomainError("not_found", "Job not found", http_status=404)
            result = record(j)
            result.pop("payload")  # Don't expose internal audio paths.
            return result

    @app.post("/api/integrations/google/sync", dependencies=protected, status_code=202)
    def sync_google():
        return enqueue(uid(), "sync", {})

    @app.post("/api/jobs/{job_id}/retry", dependencies=protected)
    def retry(job_id: str):
        with db.sessions.begin() as s:
            db.lock(s)
            j = s.get(Job, job_id)
            if not j:
                raise DomainError("not_found", "Job not found", http_status=404)
            if j.status != "failed" or j.kind == "execute":
                raise DomainError("invalid_state", "Only failed capture/sync jobs can be retried")
            if j.conversation_id and s.scalar(
                select(Job).where(
                    Job.conversation_id == j.conversation_id, Job.status.in_(["queued", "running"])
                )
            ):
                raise DomainError("busy", "Conversation already has a pending turn")
            j.status, j.attempts, j.error = "queued", 0, None
            return {"id": j.id, "status": j.status}

    static_dir = Path(__file__).resolve().parents[2] / "web"
    # Source checkout has frontend at repository root; image uses /app/web.
    if not static_dir.exists():
        static_dir = Path.cwd() / "frontend" / "dist"
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/")
        def index():
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()
