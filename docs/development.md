# Development and local setup

## Requirements

- Python 3.12, Node 22.12 or later, and npm (the frontend records npm 11.21.1).
- For AI capture: FFmpeg, whisper.cpp (`whisper-cli`), llama.cpp (`llama-server`), and the two selected models.
- Manual calendar CRUD, unit tests, and browser tests do not require models or Google credentials.

## Install

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps -e .
npx --yes npm@11.21.1 ci --prefix frontend
```

On a Mac with Homebrew:

```bash
brew install ffmpeg llama.cpp whisper-cpp
.venv/bin/python scripts/download_models.py
```

The model download is approximately 2.8 GiB. `models.lock.json` records exact revisions and SHA256 digests; the downloader verifies artifacts and reuses matching files. Model binaries are ignored by Git. The tested native versions are llama.cpp 0.7.0 (b11669) and whisper.cpp 1.9.5. Updating them requires rerunning model evaluation, since templates and parsers can change.

## Run

```bash
.venv/bin/python scripts/dev.py
```

Open [the development UI](http://127.0.0.1:5173). The launcher creates a private `.env` with a random `JARVIS_TOKEN` on first use; paste that token into the workspace login. It starts the API, worker, frontend, and model server. Ctrl+C stops its own child processes.

If llama-server is already running on port 8081, use `--no-model`. To try manual calendar CRUD without inference dependencies, use `--calendar-only`.

Default ports: frontend 5173, API 8000, model 8081. All native development listeners bind to localhost. Phone access requires a trusted HTTPS endpoint/private network setup; plain HTTP to a LAN IP cannot record microphone audio. Do not expose model or MCP services publicly. The website stores the access token in tab-scoped session storage; Lock workspace clears it.

Copy `.env.example` when you need custom data/model paths or a timezone. The default timezone is Asia/Singapore. Database/audio/OAuth files live in `data/`, which is ignored by Git. Avoid placing real personal data in a synced/cloud-backed directory if keeping it on owned hardware is required.

## Google Calendar (optional)

1. Enable Google Calendar API in a Google Cloud project.
2. Configure an OAuth consent screen and a **Desktop app** OAuth client. Add your account as a test user if the consent app is in testing.
3. Download the client JSON into an ignored private path, such as `data/google-client.json`.
4. Create/select a test calendar before using personal events, then run:

```bash
.venv/bin/python -m jarvis.google --client-secrets data/google-client.json --calendar-id YOUR_CALENDAR_ID
```

This opens Google's explicit authorization flow and saves local refresh credentials with restricted permissions. The initial OAuth scope allows Calendar access; the adapter operates only on the selected calendar. Do not commit these files. A testing consent app may require renewed authorization when its test credentials expire.

Reload Jarvis and select **Sync Google Calendar**. Add the same Google account in Apple Calendar to see these events on the phone. Independent iCloud calendars are not connected by this adapter. A normal refresh covers the previous 31 days and next 93 days; an approved provider operation refreshes its own requested time window before writing. Calendar metadata CRUD is local-only in V1; provider entries support single timed event CRUD. Recurring/all-day entries are view-only.

## Tests

```bash
.venv/bin/ruff check backend tests scripts
.venv/bin/ruff format --check backend tests scripts
.venv/bin/pytest --cov=jarvis --cov-fail-under=80 --cov-report=term-missing
npm run test --prefix frontend
npm run build --prefix frontend
npm exec --prefix frontend -- playwright install chromium
npm run test:e2e --prefix frontend
```

The browser suite starts an isolated API/worker on port 8000 and serves the built frontend with production security headers. Run the frontend build first. Stop the normal development stack first. It uses temporary data and verifies that proposals do not create events before acceptance. Both desktop and mobile viewports run the create/edit/delete flow.

Actual model evaluation is explicit, local, and isolated from personal calendars:

```bash
# Start llama-server separately, or leave the model process from a development session running.
.venv/bin/python scripts/evaluate_local.py
# Optional full speech-to-proposal evaluation with a local recording:
.venv/bin/python scripts/evaluate_voice.py /absolute/path/to/a-test-recording.wav
```

The text evaluation covers create, missing-details clarification, update, and delete using actual Qwen inference and the real stdio MCP server. The voice script additionally runs FFmpeg and Whisper. These are small smoke evaluations, not statistical accuracy benchmarks.

## Migrations and recovery

The launcher runs Alembic migrations before starting services. For separately launched services or an existing deployment, stop workers and run `.venv/bin/alembic upgrade head` before restarting. API/worker bootstrap creates a new schema for first-use convenience; do not rely on `create_all` to upgrade an existing database. Back up the SQLite database consistently before upgrades.

Approval produces a durable execution record. If a provider response is uncertain, the UI/API must reconcile the **same proposal ID** through `POST /api/proposals/{id}/retry`; do not submit a new create request. Stale/conflicting proposals require a fresh review. Failed capture/sync jobs can be retried from the conversation UI. Raw audio from failed transcription expires after 24 hours; a retry after expiry requires a fresh recording.

## Portable CPU container

```bash
# Set JARVIS_TOKEN in .env and download models first.
docker compose up --build
```

Open localhost:8000. The image contains the built UI/API, FFmpeg, and pinned CPU inference binaries. Three services run the API, worker, and model; only the API port is exposed on localhost. The data volume is persistent and private to this deployment. Native Mac development is preferred when testing Metal acceleration. Hosting, DNS/TLS, public access, and server provisioning remain deferred.
