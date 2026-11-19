# Phase 10 verification and handover

Verification dates: 2026-11-18 and 2026-11-19. Target: Linux amd64 containers on Windows Docker Desktop. This report distinguishes real integrations from deterministic test fixtures. No cloud deployment, repository visibility change, model retraining, or new project license was introduced.

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
| TomTom Flow and Incidents | Verified using real services | Dedicated provider endpoint ACTIVE; 2026-11-19 clean-clone smoke retrieved 159 incidents. Counts are time-dependent, not guaranteed. Missing-key configuration explicitly reported `not_configured`. |
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

Phase 10 source commit: **`aef6741` — `Complete Phase 10 - Dockerization and System Verification`**. A local `git clone --no-hardlinks` of that commit built and ran with fresh volumes. The only subsequent code change removes the withdrawn advisory exception from the CI audit; it does not change application behavior. Published successfully on 2026-11-19 as `d93705a7429ce577d87da78c7683257b1ae0a673`, including the stricter advisory check and verification notes. `git ls-remote origin refs/heads/master` matched the local SHA. GitHub confirms the repository remains private and its default branch is now `master`. The subsequent documentation-only handover commit records the hosted CI result below; use `git rev-parse HEAD` or the repository commit list for its exact SHA. The tested application commit remains `d93705a`.

## 5. CI

[RouteX CI](../.github/workflows/ci.yml) runs on `master`/`main` pushes, pull requests and manual dispatch. Actions are pinned to verified immutable revisions with read-only repository permission. Jobs run npm lint/TypeScript/build and advisory checks; repository hygiene; Compose validation; runtime/test image builds; real PostGIS backend tests with external transport fixtures; pip-audit; and nginx API/nested-route checks. CI cleanup targets its own disposable volumes.

Actual GitHub execution: [run 44466687241](https://github.com/roop2006/RouteX/actions/runs/44466687241) was triggered by the push of `d93705a`. **Both jobs completed successfully** on 2026-11-19. The GitHub Linux runner checked out the published source, built all runtime/test images, started fresh Compose services, passed **112 tests, 1 opt-in skip, 43 warnings in 6.74 seconds**, passed Python dependency checks and nginx proxy/nested-route checks, and cleaned up its disposable stack. The frontend job passed npm install, lint, TypeScript/production build and both advisory scans. The final handover commit changes documentation only and uses `[skip ci]`; the application and CI code are identical to this successful run. No frontend unit-test framework existed, so none is falsely claimed. CI generates a black-frame clip only to exercise job lifecycle; this is not evidence of real detections. The optional real-video streaming acceptance is documented separately to avoid expensive provider/video work on every push.

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
| Isolated installation | Source-only directory excluding local env, virtualenv, node_modules, videos and raw datasets; fresh named volumes; required models loaded/downloaded through documented preparation. A separate local clone of committed source `aef6741` also built all three images, initialized fresh volumes, opened the dashboard, passed 112 tests (1 opt-in skip; 10.56 seconds), and passed real provider, uploaded-video and streaming checks on 2026-11-19. No uncommitted application files were copied into it. The supplied local video was acceptance-test input only; it is not a startup dependency. |
| Persistence / restart | DB, Redis, backend and consumer restarted; readiness recovered. Counts unchanged across restart: roads 5, intersections 6, prediction history 10, stream events 21, alerts 183. Real provider/streaming checks rerun. The clean-clone restart independently preserved roads 5, intersections 6, predictions 5, stream events 14 and alerts 171, with readiness and provider checks passing after restart. |
| Production routing | `/api/health/ready`, redirected `/api/roads`, `/api/intersections`, nested SPA routes returned 200. nginx retains `/api` and public host/port through FastAPI redirects. |
| Python advisory audit | **89 packages audited, zero known vulnerabilities** after targeted updates. The report lists 91 installed packages, but pip-audit skips the `+cpu` torch/torchvision distributions. A separate audit of matching upstream versions `torch==2.14.0` and `torchvision==0.29.0` also found no known vulnerabilities; this checks release advisories, not CPU binary integrity. This applies to the verified Docker environment, not an assertion that the pre-existing native virtualenv was upgraded. |
| Hosted GitHub CI | **Passed**, both frontend and integration jobs, [run 44466687241](https://github.com/roop2006/RouteX/actions/runs/44466687241), source `d93705a`. |
| npm production audit | **Zero advisories** (`--omit=dev`). |
| npm full toolchain audit | **Zero findings on 2026-11-19**. The previously reported picomatch advisory was withdrawn by GitHub at 2026-11-18 15:38:56 UTC. The temporary CI exception was removed; all high/critical findings fail. |
| Secrets and repository size | Configured secret compared against changed files and reachable history without printing values; no match found. Historical `.env` was empty. Final tracked-file guard passed with zero findings. Configured-secret comparison covered 235 tracked paths and 1,938 historical blobs, with no matches. |
| Base-image OS vulnerability scan | Not performed; package audits do not establish image OS security. |

Phase 10 acceptance is complete: source preservation, reproducible Docker setup, clean installation, real integration checks, documentation, security review, GitHub publication and hosted CI are verified. No unresolved installation or publication blocker remains.

## 8. Remaining operator actions and limits

- Verification stacks were stopped after acceptance, with all named volumes preserved and ports 5173/8001 free. Existing native PostgreSQL and legacy Kafka/Redis services were not removed. Start the normal application from the repository root using the command above.
- Supply your own TomTom credentials and ensure required products/quotas. External routing, maps and model download require network access.
- Repeat dependency and base-image security reviews regularly; scan results are time-dependent.
- Keep deployment on loopback. Add authentication, authorization, TLS, quotas, retention and durable jobs before broader exposure.
- Job metadata and provider caches are in memory. Restart interrupts active video jobs; stored uploads persist but old job lookup does not.
- Geographic references and existing ML models have limited domain/calibration. TomTom has no measured vehicle counts; insufficient-input states are intentional.
- No project-wide license has been assigned; repository remains private. Public redistribution requires an owner decision and review of dependency/model/data terms.
- No historical training datasets or large videos are included. Users supply permitted footage. Physical camera/GPU/ARM64 and backup restoration were not acceptance-tested.
