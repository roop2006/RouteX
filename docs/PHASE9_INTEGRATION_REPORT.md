# RouteX Phase 9 integration repair

Verified 2026-11-15. Scope: existing Phases 1–9 only. No model training, architecture replacement, broker replacement, or Phase 10 work.

## A. Root causes

| Reported component | Finding and repair |
|---|---|
| Redis live cache | Docker was stopped/unreachable. The installed redis-py retried despite `retry_on_timeout=False`: a direct failed probe took 26.31 seconds. Alert evaluation multiplied those waits. Explicit zero retries, 0.5-second socket limits and a 15-second shared backoff bound failures. Compose services were started. Timestamp-less/future/stale cache entries are rejected. |
| TomTom Flow | Credentials and real endpoint worked outside the network sandbox (0.64 s). Redis waits delayed the endpoint and made provider failures appear broader. Responses now validate required measurements, use shorter bounded timeouts and temporary failure backoff. Missing counts/classes are no longer invented. |
| OSRM | A real request succeeded in 0.59 s; earlier sandbox connection errors were not provider authentication failures. Alternative probes previously compounded delays. Via requests now run concurrently with bounded candidates; fallback behavior remains. |
| Alert rules/persistence | Tables and 10 default rules existed and were queryable. Redis waits, deduplication shortcuts that discarded incident updates, point-only matching, missing incident refresh, and no route-ID restriction were integration defects. PostgreSQL remains authoritative, with serialized evaluation, updates by provider identity, notifications on creation, scoped absence reconciliation, full-geometry matching and route isolation. A database error now rolls back before subsequent probes. |
| YOLO | No job-state health endpoint existed. The uploaded-video worker now reports idle when waiting, running when jobs exist, degraded after a failed job, and missing model configuration. Real sample-frame inference succeeded (12 detected vehicles); no training was performed. |
| TomTom Incidents | Real API access succeeded (13 incidents in the initial probe). Cache keys rounded boxes without expanding the actual request, risking missed incidents; malformed payloads were accepted as empty success. Boxes now expand outward, schemas validate, and successful empty, unavailable, unconfigured and stale responses remain distinct. |

Additional findings: the old backend process accepted connections but timed out even on `/health`; it was identified as this checkout's Uvicorn reloader and restarted. Hardcoded historical corridor seeding and TomTom-derived invented vehicle distributions were pre-existing issues; automatic seeding stopped and operational queries exclude that provenance while preserving records. Nullable metrics and a unique nullable stream identity were added through the existing migration helper. Kafka storage previously committed observations before alert evaluation, allowing duplicates after retries; the transaction and identity now cover both.

## B. Changed files

The complete per-file inventory follows below. The original working tree was clean at checkpoint `1605350`. No credentials or model artifacts were changed.

| File | Purpose |
|---|---|
| `README.md` | Link current verification and startup instructions. |
| `progress.md` | Record repair results and supersede earlier network blockers. |
| `docs/TOMTOM_INTEGRATION.md` | Correct metric provenance and model input documentation. |
| `docs/PHASE9_INTEGRATION_REPORT.md` | This root-cause, verification and operating report. |
| `backend/app/api/ai_live.py` | Reject prediction requests without measured required inputs. |
| `backend/app/api/alerts.py` | Add route provider snapshot and current incident reconciliation. |
| `backend/app/api/geo.py` | Hide legacy invented provider counts and exclude fixed-profile seeds. |
| `backend/app/api/health.py` | Report evidence-based service states and recover sessions after failed probes. |
| `backend/app/api/live_traffic.py` | Refresh selected route telemetry and reconcile incident lifecycle. |
| `backend/app/core/apply_migrations.py` | Add nullable metrics and unique nullable stream event identity non-destructively. |
| `backend/app/core/config.py` | Resolve environment configuration from the repository root. |
| `backend/app/core/database.py` | Bound database connection, pool and statement waits. |
| `backend/app/main.py` | Keep diagnostics accessible on initialization failure; stop synthetic traffic seeding. |
| `backend/app/models/traffic_stream_event.py` | Model missing measurements and durable source identity. |
| `backend/app/schemas/alerts.py` | Validate geometry and timestamps; model route snapshot and marker association. |
| `backend/app/schemas/traffic_event.py` | Permit unavailable measurement values. |
| `backend/app/schemas/user_analysis.py` | Carry nullable observations and provider availability. |
| `backend/app/services/alert_service.py` | Serialize persistence, deduplicate updates, reconcile incidents, match full geometry and isolate routes. |
| `backend/app/services/live_traffic_service.py` | Preserve real measurements and freshness; remove invented counts and fix UTC handling. |
| `backend/app/services/route_analysis_service.py` | Reuse corridor queries, refresh route inference from measured inputs, bound alternate probes and exclude synthetic data. |
| `backend/app/services/tomtom_traffic_service.py` | Bound requests, validate provider responses, expand cache boxes, preserve incident metadata and null missing metrics. |
| `backend/app/services/traffic_ingestion_service.py` | Retain compatibility entry point while disabling fixed historical-profile seeding. |
| `backend/app/services/traffic_service.py` | Exclude synthetic provenance and hide legacy fabricated provider metrics on reads. |
| `backend/app/services/video_analysis_service.py` | Report idle/running/failed worker and model states accurately. |
| `frontend/src/api/alerts.ts` | Request shared route alert snapshots. |
| `frontend/src/api/userAnalysis.ts` | Bound route analysis client timeout. |
| `frontend/src/components/dashboard/TrafficChart.tsx` | Accept nullable traffic measurements. |
| `frontend/src/components/map/TrafficMap.tsx` | Display selected route incidents on the existing map. |
| `frontend/src/components/map/TrafficMarker.tsx` | Display unavailable counts without null text. |
| `frontend/src/components/map/RouteAlertLayer.tsx` | Share route alert query, deduplicate markers, show incident details and route overlay. |
| `frontend/src/contexts/SelectedRouteProvider.tsx` | Share selected geometry, refreshed corridor, predictions and incident status. |
| `frontend/src/features/alerts/AlertsPage.tsx` | Show route-scoped alerts, provider failures, route distance and accurate empty state. |
| `frontend/src/features/analysis/AnalysisPage.tsx` | Exclude missing measurements from computed summaries. |
| `frontend/src/features/live-traffic/LiveTrafficPage.tsx` | Display missing metrics and incidents without fabricating defaults. |
| `frontend/src/features/overview/OverviewPage.tsx` | Use selected route assets, observations and predictions. |
| `frontend/src/features/predictions/PredictionsPage.tsx` | Disable unrelated live inference while viewing a selected route. |
| `frontend/src/features/route-analysis/components/RouteMap.tsx` | Add synchronized incident markers to the existing route map. |
| `frontend/src/features/system/SystemStatusPage.tsx` | Render verified/degraded/idle/unconfigured states. |
| `frontend/src/hooks/useAlerts.ts` | Key route snapshots by geometry; share bounded polling. |
| `frontend/src/hooks/useLiveTraffic.ts` | Use shared route traffic/incidents; avoid global polling in route mode. |
| `frontend/src/types/alerts.ts` | Type route snapshot, route reference and marker coordinates. |
| `frontend/src/types/geography.ts` | Model unavailable event metrics. |
| `frontend/src/types/traffic.ts` | Model nullable live/stream measurements. |
| `frontend/src/types/userAnalysis.ts` | Type nullable route observations and provider errors. |
| `frontend/src/utils/formatters.ts` | Format missing values and interpret naive backend timestamps as UTC. |
| `tests/test_alerts.py` | Isolate event identities and allow unrelated real persisted alerts. |
| `tests/test_connectivity_reliability.py` | Isolate Redis breaker state in unit tests. |
| `tests/test_live_traffic_and_ingestion.py` | Check prediction input availability instead of invented provider counts. |
| `tests/test_tomtom_integration.py` | Validate measured-input inference and explicit insufficient-data state. |
| `tests/test_route_alert_regressions.py` | Cover full geometry, lifecycle, route changes, malformed providers, outages and durable deduplication. |
| `tests/test_streaming_live.py` | Opt-in real sample-video/Kafka/PostGIS/Redis/FastAPI acceptance test with isolated storage. |
| `vision/streaming/event_storage.py` | Persist observation and alerts atomically with durable Kafka identity. |
| `vision/streaming/kafka_config.py` | Load environment-driven broker/topic/group settings. |
| `vision/streaming/kafka_producer.py` | Add UTC timestamps and bounded startup/send; support installed Kafka timeout option. |
| `vision/streaming/redis_client.py` | Disable implicit retries, bound sockets, back off failures and validate cache timestamps. |

## C. Integration verification

| Component | Status | Evidence / limit |
|---|---|---|
| FastAPI | PASS | Restarted local server; HTTP health, live traffic, alerts and model registry requests succeeded. |
| PostgreSQL/PostGIS | PASS | PostGIS 3.6; additive migration; real spatial/persistence regression tests. Existing records retained. |
| Redis | PASS | Compose running, real PING; outage behavior and TTL regression tests. |
| Kafka | PASS | Real temporary-topic publish/consume roundtrip and complete sample-video pipeline; topic removed afterward. Durable and cache deduplication passed. |
| YOLO worker | PASS | Existing artifact processed 12 sample-video frames; measurements reached Kafka, PostgreSQL, Redis and FastAPI. Idle state verified. |
| OSRM | PASS | Real external routing and route integration tests succeeded. |
| TomTom Flow | PASS | Real authenticated retrieval/cache tests and latency probe succeeded. |
| TomTom Incidents | PASS | Real retrieval plus fixture-based empty/invalid/timeout/update/expiry tests. |
| Route Planning | PASS | Browser route calculation and real provider/PostGIS regression tests. |
| Traffic Analysis | PASS | Selected route corridor and nullable metrics retained; synthetic benchmark provenance excluded. |
| Roads | PASS | Existing 250 m PostGIS corridor queries and route response tests. |
| Intersections | PASS | Existing 350 m PostGIS corridor queries and route response tests. |
| AI Predictions | PASS | Existing artifacts, inference, history and evaluation tests. Routes without measured counts correctly return insufficient data. |
| Alerts | PASS | Real PostgreSQL lifecycle, rule, full geometry, route change, failure and deduplication tests; route panel observed in browser. |
| System Status | PASS | Distinct healthy/degraded/unavailable/not-configured/idle/unverified states; Kafka TCP alone never claims consumer health. |

These statuses describe the evidence above, not a guarantee of continuous availability. Browser console retained Vite websocket errors from the interrupted development server; the page loaded and navigation worked after restart/reload. The sample-video acceptance test invokes the existing consumer processing function on a real broker message; it does not verify a continuously running consumer daemon or a physical camera.

## D. Tests executed

Commands were run from `C:\Dev\RouteX`, using network/database access outside the restricted sandbox where necessary.

```powershell
$env:ROUTEX_RUN_STREAMING_SMOKE='1'
.\.venv\Scripts\python.exe -m pytest -q --disable-warnings --basetemp .pytest-temp/complete-final
# Final full suite: 110 passed, 484 warnings, 27.83 seconds
.\.venv\Scripts\python.exe -m pytest -q --disable-warnings --basetemp .pytest-temp/verified-nov15
# Earlier full suite without the opt-in streaming test: 109 passed, 447 warnings, 26.53 seconds
.\.venv\Scripts\python.exe -m pytest tests/test_route_alert_regressions.py tests/test_alerts.py -q --disable-warnings --basetemp .pytest-temp/final-focused
# 19 passed, 35 warnings, 11.27 seconds after the stale observation alert filter
.\.venv\Scripts\python.exe -m pytest tests/test_phase_integration.py tests/test_route_alert_regressions.py -q --disable-warnings --basetemp .pytest-temp/geo-final
# 22 passed, 14 warnings, 10.81 seconds after geospatial null-metric changes
npm --prefix frontend run lint
# Passed
npm --prefix frontend run build
# Passed; existing bundle warning above 500 kB
.\.venv\Scripts\python.exe -m compileall -q backend vision
# Passed
```

The initial full run reported 89 passed/5 failed; the resumed run reported 107 passed/2 failed. Those failures were corrected, including outdated assumptions that TomTom supplies measured vehicle counts and test circuit-breaker state leaking between tests. The first real streaming acceptance test also caught an unsupported producer timeout configuration; the producer now selects the option supported by the installed Kafka library. New incident and streaming tests use a rolled-back PostGIS transaction. The streaming test prefixes Redis keys and deletes its temporary Kafka topic and cache entries. Existing older integration tests still write test observations through their original endpoints.

Additional live scripts: configured-provider probes; KafkaAdminClient temporary-topic producer/consumer roundtrip (true); VehicleTracker + TrafficProcessor inference on `data/videos/traffic.mp4` (12 observed vehicles). The live traffic endpoint measured 0.641 seconds after repair versus the initial Redis probe alone taking 26.31 seconds; these are individual observations, not a load benchmark.

Final HTTP probes returned 200: `/health` 0.016 s, `/live-traffic/` 0.703 s, `/live-traffic/incidents` 1.359 s, `/health/integrations` 0.047 s. At that instant diagnostics reported PostgreSQL/Redis/alert storage healthy, TomTom Flow/Incidents available, Kafka degraded (TCP-only probe), YOLO idle and OSRM unverified (no recent request in that server process); separate real routing checks passed.

## E. Remaining limitations

- TMC direction and road numbers are retained. OSRM geometry has no corresponding TMC location reference, so direction compatibility remains explicitly `UNVERIFIED`; a corridor match indicates possible impact, including nearby parallel roads. No guarantee of safe travel is made.
- Incident lifecycle refresh is request-driven. Run the existing Kafka consumer for continuous camera-event processing. The UI polls only while active; no new scheduler or notification service was introduced.
- The health endpoint verifies Kafka TCP reachability only and labels it degraded until consumer functionality is separately established; it does not infer consumer health from an open port.
- Physical camera operation and a long-duration workload remain operational acceptance checks. The real sample-video pipeline passed using existing detection, tracking, lanes, direction, speed estimation, broker, consumer processing, persistence and API code.
- Missing provider vehicle counts are null. The production model needs measured vehicle count, speed and density; TomTom alone cannot satisfy that input contract. Model artifacts and training code remain unchanged.
- Existing legacy synthetic/test rows are preserved. Legacy fixed-profile provenance is excluded from operating analytics; historical test observations created by older tests may still exist.
- Local PostgreSQL, Docker Desktop, Redis/Kafka and provider access must be running after machine restarts. Keys remain in the existing environment configuration.

## F. Phase 9 status

The Phase 9 code integration and automated acceptance checks are complete, including the real sample-video pipeline. Sustained production operation is not certified; the camera deployment and direction-reference limitations above remain. Phase 10 was not started.

## G. Start and verify locally

Open PowerShell at `C:\Dev\RouteX`. Start Docker Desktop. If PostgreSQL is stopped, use an elevated PowerShell for the service command:

```powershell
Start-Service postgresql-x64-18
docker compose up -d redis kafka
.\.venv\Scripts\python.exe -m backend.app.core.apply_migrations
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8001
```

In a second terminal:

```powershell
Set-Location C:\Dev\RouteX
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173
```

For the existing streaming pipeline, use separate terminals:

```powershell
Set-Location C:\Dev\RouteX
.\.venv\Scripts\python.exe -m vision.streaming.kafka_consumer
# Another terminal, using the repository's sample video and camera configuration:
.\.venv\Scripts\python.exe -m vision.traffic_demo
```

Open http://127.0.0.1:5173. Calculate a route; inspect Traffic Analysis, Roads, Intersections, Alerts and the map; change the destination and verify old route results clear. Use Video Analysis for the existing uploaded-video worker. Verify diagnostics:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-RestMethod http://127.0.0.1:8001/health/integrations
Invoke-RestMethod http://127.0.0.1:8001/live-traffic/
```

Provider field validation was checked against the official [Incident Details v5](https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/traffic-incidents/incident-details) and [Flow Segment Data](https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/traffic-flow/flow-segment-data) documentation.
