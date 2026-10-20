# Initial V1 validation — 20 October 2026

The first implementation was tested locally on the development Mac and through GitHub Actions on Linux. This is a prototype validation record, not a general model-accuracy benchmark.

- Backend: time/DST, conflicts, approval/version/idempotency, API auth/uploads, durable jobs, real stdio MCP, and mocked Google sync/timeouts. Coverage is approximately 86%, with an 80% CI minimum.
- Frontend: three request/auth/error tests and a successful production build.
- Browser: real local API/worker create → review → accept → edit → delete flows on desktop and mobile Chromium viewports, using the built UI and production security headers.
- Actual inference: Qwen3-4B-Instruct-2507 Q4_K_M through native llama.cpp, with actual MCP calls and an isolated database. Create, missing-details clarification, update, and delete passed. The delete case allowed a target-confirmation follow-up; the small model sometimes asks that extra question.
- Actual speech: a synthetic English recording was transcribed by Whisper small.en and produced a validated pending calendar proposal. A warm standalone run took approximately 1 second for transcription and 9.4 seconds total on this Mac; cold starts were slower. This does not predict an 8 GB shared-CPU cloud instance's latency.
- Assembled HTTP path: typed and synthetic voice inputs traversed the actual API, durable worker, local models, and MCP server. Proposals were inspected and cancelled, without publishing events.

Real-model tests exposed two important integration issues: supplying authoritative calendar IDs prevented name/ID confusion, and local date/time tool fields removed UTC arithmetic from the model. A strict HH:MM schema prevents RFC time offsets from being misinterpreted. UI success is based on actual proposal/execution state, rather than model prose.

Live Google OAuth and a real account calendar have not been connected; Google behavior is covered by controlled HTTP fixtures. Phone hardware microphone capture over the LAN still needs trusted HTTPS. No cloud host or server deployment has been provisioned.

The Linux image build and application smoke test run in CI because Docker is not installed on the development Mac. The first image smoke caught an installed-package/static-asset lookup issue; the asset directory is now explicit (`JARVIS_WEB_DIR`) and has a regression test.
