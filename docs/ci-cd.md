# CI/CD

## Continuous integration

`.github/workflows/ci.yml` runs on main pushes, pull requests, manual dispatch, and reusable workflow calls:

1. **Backend:** Install locked Python dependencies; lint/format; run tests with an 80% coverage floor; upgrade/check/downgrade/re-upgrade migrations.
2. **Frontend:** Install locked dependencies with npm 11.21.1; run unit tests and production build; install Chromium and run desktop/mobile integration tests against an isolated API and worker.
3. **Container:** Build the complete Linux CPU image, verify inference executables, and smoke-test the built UI and authenticated calendar API.

Coverage and browser failure traces/screenshots are uploaded as artifacts. CI has read-only repository permissions. No models, personal recordings, Google credentials, or paid services are required. The real MCP subprocess is exercised with a temporary SQLite database; model and provider responses are controlled in deterministic tests.

## Delivery

The **Release container** workflow is manually dispatched with a version such as `v0.1.0`. It reruns CI and only publishes after every check passes. The image is published to `ghcr.io/nitant-p/jarvis` with the requested version and a commit-based tag. GitHub's built-in token supplies package publishing permission; no long-lived registry token is needed.

This implements tested artifact delivery. It does **not** deploy to DigitalOcean or run migrations on a live host. Hosting is intentionally shelved. Once a target exists, add a separately reviewed deploy job that pins an image digest, backs up the database, applies migrations, runs health checks, and supports rollback. No host addresses or deployment credentials are currently stored.

## Reproducibility

- `requirements.lock` and `requirements-dev.lock` pin Python packages.
- `frontend/package-lock.json` pins npm packages; npm 11.21.1 is recorded because npm 10 failed resolving optional test-tool peers in this environment.
- `models.lock.json` pins model revisions/checksums, without committing weights.
- `Dockerfile` pins the llama.cpp and whisper.cpp source commits; Linux binaries are compiled without host-specific CPU instruction assumptions.
- Dependency updates are separate changes that rerun tests. Dependabot checks npm packages and Actions weekly; Python lockfiles are regenerated with pip-tools when updating project dependencies.

Model evaluations remain a separate local check. Changing a model, quantization, runtime, or template should rerun `scripts/evaluate_local.py` and a representative voice recording. Passing application tests alone does not establish model comprehension quality.
