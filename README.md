# Jarvis

A private voice-to-calendar assistant. Record or type a note, clarify missing details, review the proposed change, and put it on your calendar.

**Status:** Working V1 prototype. Develop locally on Mac; portable CPU-only Linux container provided. Hosting and schedule optimization are deferred.

## What works

- Local English transcription with Whisper `small.en` / whisper.cpp.
- Local Qwen3-4B-Instruct-2507 Q4_K_M inference through llama.cpp.
- A private MCP tool bridge for event search and calendar/event CRUD proposals.
- Phone-friendly calendar UI, manual editing, voice/typed clarification, and Accept/Edit/Cancel.
- Deterministic local-time conversion, conflict detection, stale-version checks, and duplicate-safe execution.
- Durable SQLite jobs, local storage, audit records, audio cleanup, and retries.
- An optional Google Calendar adapter; Google-backed events can appear in Apple Calendar. OAuth setup is required.

Long-term goal planning, automatic optimization, recurring/all-day mutations, and evening planning notifications are outside this first slice.

## Start locally

Requires Python 3.12 and Node 22.12+:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps -e .
npx --yes npm@11.21.1 ci --prefix frontend
brew install ffmpeg llama.cpp whisper-cpp
.venv/bin/python scripts/download_models.py
.venv/bin/python scripts/dev.py
```

Open [localhost:5173](http://127.0.0.1:5173). The launcher creates a random access token in the ignored `.env` file on first run; use it to unlock the workspace. Model downloads total approximately 2.8 GiB and are checksum-verified. Ctrl+C stops the development processes.

For manual calendar editing without models, run `scripts/dev.py --calendar-only`. Use `--no-model` if llama-server is already running. Phone microphone capture requires trusted HTTPS when accessing the host over a network; localhost works for desktop testing.

See [development instructions](docs/development.md) for configuration, Google OAuth, model evaluation, migrations, and Docker Compose. Personal data, recordings, credentials, and model weights are excluded from Git. Cloud hosting is a future data-location decision.

## Architecture

![Implemented runtime](docs/architecture/runtime.svg)

[Architecture and data flow](docs/architecture.md) · [Editable Mermaid source](docs/architecture/runtime.mmd)

The LLM interprets language and invokes read/proposal tools. Application code resolves times and validates changes. Only the authenticated user's acceptance can enqueue an actual calendar mutation.

## Tests and CI/CD

```bash
.venv/bin/ruff check backend tests scripts
.venv/bin/ruff format --check backend tests scripts
.venv/bin/pytest --cov=jarvis --cov-fail-under=80
npm run test --prefix frontend
npm run build --prefix frontend
npm exec --prefix frontend -- playwright install chromium
npm run test:e2e --prefix frontend
```

GitHub Actions checks Python tests/coverage, migrations, frontend tests/build, desktop/mobile browser flows, and a Linux container smoke test. The manual release workflow publishes a versioned GHCR image only after those checks pass. Live server deployment remains deferred. See [CI/CD details](docs/ci-cd.md).

The local-model smoke evaluation is separate: `scripts/evaluate_local.py` uses actual Qwen inference and the real MCP subprocess, without personal data or Google credentials. `scripts/evaluate_voice.py` adds real speech transcription. These small checks do not establish accuracy across arbitrary recordings.

## Planning documents

- [Product requirements and roadmap](docs/product-plan.md)
- [Original V1 architecture proposal](docs/architecture-v1.md)
- [Cloud hosting research](docs/cloud-hosting-research.md)
- [Initial validation and limitations](docs/validation.md)
