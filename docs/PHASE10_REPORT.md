# Phase 10 verification and handover

Verification date: 2026-11-18. Target: Linux amd64 containers on Windows Docker Desktop. This report distinguishes real integrations from deterministic test fixtures. No cloud deployment, repository visibility change, model retraining, or new project license was introduced.

## 1. Architecture

The [architecture inventory](ARCHITECTURE.md) records the existing implementation. nginx serves React and proxies `/api` to one FastAPI worker. FastAPI uses PostgreSQL/PostGIS, Redis, existing serialized ML models, external OSRM and TomTom. Its existing thread pool runs uploaded-video jobs with CPU YOLO/OpenCV. A separate existing Kafka consumer persists validated stream events and evaluates alerts. Browser maps retain OpenStreetMap attribution. TomTom caches are process-local; Redis stores stream snapshots and advisory alert keys. These are separate communication paths, not one mandatory serial pipeline.

## 2. Docker and initialization

Added multi-stage backend/runtime-test and frontend/nginx images, Compose runtime/development/test configurations, build exclusions, pinned Python dependencies, checksum-verified model preparation, database and Kafka initialization, readiness checks, loopback listeners, resource/log limits and non-root application users. The initial Kafka volume ownership helper is the narrow root exception.

The stack contains `db`, `redis`, `kafka`, `kafka-volume-init`, `kafka-init`, `initialize`, `backend`, `consumer`, and `frontend`. One-shot initializers terminate successfully. PostgreSQL schema/reference creation and topic creation are additive/idempotent. Named volumes hold PostgreSQL, Redis AOF, Kafka logs and uploaded files. The default project name is `routex-stack`, avoiding the pre-existing developer Kafka/Redis project.

```sh
docker compose --env-file .env.docker up -d --build
docker compose --env-file .env.docker ps -a
docker compose --env-file .env.docker stop
```

Create `.env.docker` from `.env.example` first and set a unique database password. Keep the native `.env`. `down` preserves named volumes; `down -v` destroys them and is only appropriate for explicitly disposable tests. See [operations and backup/restore](DOCKER.md).

## 3. Functionality and evidence classification

| Component | Classification | Evidence / limits |
|---|---|---|
| Docker images, initialization, internal networking | Verified using real services | Linux CPU images built; fresh volumes initialized and readiness passed. No host Python/Node/database needed by runtime. |
| PostgreSQL/PostGIS and geography | Verified using real services | Spatial API queries; five reference roads and six intersections; additive initialization and restart checks. References are demonstration geography, not live observations. |
| Kafka consumer, Redis and alerts | Verified using real services | Existing YOLO pipeline measured 15 vehicles from a local real video sample; producer acknowledgment, running consumer, DB event identity, Redis snapshot and API retrieval verified. Repeated successfully after restart. |
| TomTom Flow and Incidents | Verified using real services | Dedicated provider endpoint ACTIVE; final smoke retrieved 154 incidents. Counts are time-dependent, not guaranteed. Missing-key configuration explicitly reported `not_configured`. |
| OSRM | Verified using real services | Real external driving routes and integration status `available`; browser route changed from Chennai Central to Egmore and alternatives recalculated. Public endpoint has no availability guarantee. |
| Uploaded video / CPU YOLO | Verified using real services | Real MP4 uploaded and job completed. Decoding, detection and tracking ran on CPU; no GPU requirement. |
| ML models, predictions, history/evaluation | Verified using real services | Original artifact hashes preserved; production models loaded; prediction/history/evaluation APIs exercised. Numerical test inputs are fixtures, not observed traffic. |
| Dashboard / route context / nginx | Verified using real services | All 11 navigation pages loaded; route, roads, intersections, predictions and alerts shared context; changing destination cleared/recomputed context; nested reload/API redirects returned 200; no browser warning/error logs in the verification tab. |
| Timeout, fallback, malformed data, alert lifecycle/deduplication | Verified using mocks and real PostGIS | Existing focused regression suite; external HTTP transports mocked only under explicit test configuration. |
| Physical cameras, GPU, ARM64 | Implemented paths not tested in this phase | No claim of physical camera, GPU or ARM64 acceptance. CPU recorded-video path was tested. |
| Public multi-user deployment | Blocked by missing product security features | Application remains local-only without authentication/authorization, TLS or request quotas. This is outside the authorized deployment scope. |

The provider smoke originally assumed the aggregate live endpoint must return TomTom. It correctly returned fresh Redis camera data after streaming verification. The check now probes the dedicated TomTom endpoint; real Flow/Incidents/OSRM checks passed afterward. No application precedence was changed to satisfy the test.

## 4. GitHub and preservation

Repository: [roop2006/RouteX](https://github.com/roop2006/RouteX), existing branch `master`, verified private. Phase 9 was reviewed and tested before any Phase 10 implementation, then committed as **`1ea0387` — `Complete Phase 9 - Alerts and Traffic Reliability`**. Existing working changes and new source files were preserved. No reset, restore, force-push or history rewrite was used.

Phase 10 changes include Docker/CI/deployment files, dependency manifests, essential existing model artifacts, previously ignored `ml/data` source modules, architecture/operations/security documentation and genuine screenshots. Runtime changes are limited to deployment configuration, readiness/CORS/error sanitization, graceful consumer shutdown, producer acknowledgment, proxy routing and frontend loading/text fixes. The original model bytes are unchanged; the large external model is distributed compressed with its original expanded checksum.

Publication status: final source commit, fresh-clone verification and GitHub push are pending at the time of this report draft. This paragraph will be updated with observed results before handover.

## 5. CI

[RouteX CI](../.github/workflows/ci.yml) runs on `master`/`main` pushes, pull requests and manual dispatch. Actions are pinned to verified immutable revisions with read-only repository permission. Jobs run npm lint/TypeScript/build and advisory checks; repository hygiene; Compose validation; runtime/test image builds; real PostGIS backend tests with external transport fixtures; pip-audit; and nginx API/nested-route checks. CI cleanup targets its own disposable volumes.

Actual GitHub execution: not yet run; workflow configuration and corresponding local container checks are verified. No frontend unit-test framework existed, so none is falsely claimed. CI generates a black-frame clip only to exercise job lifecycle; this is not evidence of real detections. The optional real-video streaming acceptance is documented separately to avoid expensive provider/video work on every push.

## 6. Documentation

README covers the requested overview, problem, features, architecture diagram, technology, structure, screenshots, prerequisites, setup, configuration, operation, feature usage, testing, troubleshooting, decisions, future improvements, license/credits and status. Supporting documents: [Docker guide](DOCKER.md), [architecture](ARCHITECTURE.md), [security/credits](SECURITY_AND_CREDITS.md), and [contribution guide](../CONTRIBUTING.md). Older Phase 9 evidence is retained as history; the TomTom guide points to current container instructions.

Screenshots were captured from the production Docker frontend, not generated mockups: [route intelligence](screenshots/route-intelligence.jpg), [alerts](screenshots/route-alerts.jpg), [map](screenshots/traffic-map.jpg), [diagnostics](screenshots/system-status.jpg). The isolated verification database contains both real provider/video results and labelled regression fixtures; screenshots are not accuracy benchmarks.

## 7. Final verification

| Check | Observed result |
|---|---|
| Phase 9 checkpoint regression | 109 passed, 1 skipped; additional opt-in real-video streaming test: 1 passed |
| Final container backend suite, 2026-11-18 | **112 passed, 1 skipped**, 43 warnings, 13.89 seconds. Skip is the opt-in real-video test; it is independently covered by real streaming acceptance. |
| Frontend lint / production build | Passed. Lazy page loading reduced the main bundle from approximately 1.12 MB to 288 kB; no >500 kB chunk warning. No redesign. |
| Compose configuration / runtime builds | Passed; backend CPU runtime approximately 3.54 GB, nginx frontend approximately 83 MB (Docker image-reported bytes, not compressed download sizes). |
| Isolated installation | Source-only directory excluding local env, virtualenv, node_modules, videos and raw datasets; fresh named volumes; required models loaded/downloaded through documented preparation. Actual final-commit clone check pending below. |
| Persistence / restart | DB, Redis, backend and consumer restarted; readiness recovered. Counts unchanged across restart: roads 5, intersections 6, prediction history 10, stream events 21, alerts 183. Real provider/streaming checks rerun. |
| Production routing | `/api/health/ready`, redirected `/api/roads`, `/api/intersections`, nested SPA routes returned 200. nginx retains `/api` and public host/port through FastAPI redirects. |
| Python advisory audit | **91 packages audited, zero known vulnerabilities** after targeted updates. This applies to the verified Docker environment, not an assertion that the pre-existing native virtualenv was upgraded. |
| npm production audit | **Zero advisories** (`--omit=dev`). |
| npm full toolchain audit | **Known high-severity picomatch advisory, no patched upstream release on 2026-11-18**. Eleven inherited package findings refer to this advisory. Exact, development-only CI exception expires 2026-12-18; new high/critical findings fail. Full audit is not clean. |
| Secrets and repository size | Configured secret compared against changed files and reachable history without printing values; no match found. Historical `.env` was empty. Final tracked-file guard must pass before push. |
| Base-image OS vulnerability scan | Not performed; package audits do not establish image OS security. |

## 8. Remaining operator actions and limits

- Supply your own TomTom credentials and ensure required products/quotas. External routing, maps and model download require network access.
- Review the [picomatch exception](SECURITY_AND_CREDITS.md#known-development-only-advisory-2026-11-18) when upstream publishes a fix and no later than 2026-12-18.
- Keep deployment on loopback. Add authentication, authorization, TLS, quotas, retention and durable jobs before broader exposure.
- Job metadata and provider caches are in memory. Restart interrupts active video jobs; stored uploads persist but old job lookup does not.
- Geographic references and existing ML models have limited domain/calibration. TomTom has no measured vehicle counts; insufficient-input states are intentional.
- No project-wide license has been assigned; repository remains private. Public redistribution requires an owner decision and review of dependency/model/data terms.
- No historical training datasets or large videos are included. Users supply permitted footage. Physical camera/GPU/ARM64 and backup restoration were not acceptance-tested.
