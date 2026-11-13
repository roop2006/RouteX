# RouteX Integration Debugging Progress

Updated: 2026-11-06

## Findings and fixes

- `/health` only reports that FastAPI is serving requests. It does not check the database, TomTom, or individual feature endpoints. The Axios client also described every HTTP error as a backend connection failure. It now reports HTTP status and FastAPI detail, with distinct messages for authentication/configuration, missing endpoints, request validation, timeouts, and network/CORS failures.
- Traffic Analysis calls `GET /traffic-events/` with `skip`, `limit`, and optional `congestion_level`. The current working-tree response schema uses `float` for values in `direction_counts`; TomTom incident ingestion stores fractional `length_meters` there. The schema edit was already present in the workspace before this repair. It is retained, and a regression test now POSTs and GETs `119.027384658` without rounding. The database JSON column was not changed.
- The reported `int_from_float` response error could not be reproduced against the current source: `/traffic-events/` returned HTTP 200 with fractional lengths, and the existing committed `float | int` union also accepts a fractional value under the installed Pydantic version. The reported error therefore points to a runtime schema different from the current source, most likely a stale/different backend process. Restarting FastAPI after schema changes is necessary for the running app to load the current response model.
- Live Traffic calls `GET /live-traffic/`; incidents call `GET /live-traffic/incidents`. TomTom configuration loads (`is_configured=True`), but outbound requests from this machine fail with `WinError 10061` (connection refused). The incident service previously converted failures to an empty list and the endpoint labeled that result `ACTIVE`, which looked like zero incidents. The endpoint now returns HTTP 502 with a sanitized provider error. The flow endpoint still falls back to Redis/database data and includes `provider_error`; the Live Traffic page shows that reason alongside fallback data.
- Map route analysis calls `POST /analysis/route` with `{origin:{lat,lng}, destination:{lat,lng}, include_alternatives}`. The request and GeoJSON `[longitude, latitude]` geometry formats are aligned. The map listener previously discarded clicks whenever explicit “Pick on Map” mode was off, despite the page supporting direct clicks; it now forwards them.
- OSRM remains the primary routing provider. Runtime OSRM access from this machine also fails with `WinError 10061`. The existing TomTom route fallback additionally referenced a nonexistent `.session` attribute, so it could not run even if reachable. It now makes the same HTTP request through `httpx` and sanitizes provider errors. If external routing is unavailable, PostGIS still handles routes whose endpoints both match a registered road; failures now explain when that fallback does not match.
- A live route request for the preset Chennai endpoints returned HTTP 200 with a 354.1 m GeoJSON LineString and an `AVAILABLE` AI prediction. This was served by the PostGIS fallback because OSRM and outbound TomTom access failed. Existing predictor/model architecture and feature schema were left unchanged.

## Verification

- Full backend suite: **85 passed**, 4 existing deprecation warnings.
- Focused post-fix suite: **5 passed** for fractional traffic distances, live-flow fallback errors, live-incident errors, TomTom routing fallback request construction, and route analysis.
- Frontend lint: passed.
- Frontend production build: passed. Vite reports the existing large JavaScript chunk warning (>500 kB).
- Live local FastAPI checks: `/health` and `/traffic-events/` returned HTTP 200. The first direct `/live-traffic/` and `/ai/live-prediction` PowerShell requests timed out; TestClient regression checks verified the live traffic fallback and prediction paths. TomTom city snapshot returned `UNAVAILABLE` with no live junctions in this environment.
- Browser Network/console inspection was blocked because the computer-use host could not determine the current browser URL. Local Vite and FastAPI were started for the check; the browser interaction was stopped safely.

## Phase 8 route-specific dashboard refinement

Updated: 2026-11-09

### Integration changes

- Added a shared selected-route provider with the route request endpoints, selected alternative, route geometry, distance/time, route ID, and calculation time. Route form edits clear this context and its route-derived page state; selecting another alternative updates the shared selection.
- Extended the existing `POST /analysis/route` response with stable per-route IDs, corridor road/intersection matches, route-local observations, freshness and volume summaries (including free-flow speed when provider metadata contains it), and an AI result for each alternative.
- Route matching uses the existing PostGIS schema and actual OSRM/fallback LineString: roads are within 250 m and explicitly labeled intersecting or nearby; intersections and traffic observations are within 350 m; road/intersection observation summaries use a 100 m asset radius. Geometries remain SRID 4326, and geography predicates enforce metre distances.
- Traffic Analysis now displays route observations and route summary metrics without querying the general event feed while a route is selected. Roads and Intersections likewise show only matched assets in route mode and preserve general views with no route selected. The AI Predictions page displays the selected route prediction when available.
- Video analysis remains on its existing pipeline. Combined analysis remains the only path to associate video with a route; route telemetry is sourced from stored spatial observations and does not assume that standalone video has a location.
- Added response regression assertions for route IDs, per-alternative corridor/AI data, road geometry/match classification, road/intersection corridor distances, and a direct PostGIS `ST_DWithin` verification for every returned traffic observation, plus provenance/location and freshness.

### Documentation inventory and verification

- This checkout contains `docs/TOMTOM_INTEGRATION.md` and `progress.md`. The requested `architecture.md`, `build_plan.md`, `data.md`, and `evaluation.md` do not exist in the repository; no duplicate documentation files were created. The integration contract and spatial thresholds were added to the existing TomTom integration document.
- Final focused route run: **1 passed, 1 skipped**. The no-telemetry test skipped because routing failed for that endpoint pair in this environment and no matching PostGIS fallback road was available.
- Final frontend lint: **passed**. Production build: **passed** (2,697 modules); Vite reports a JavaScript chunk above its 500 kB warning threshold.
- Full backend suite: **78 passed, 5 failed, 1 skipped, 1 setup error**. The failures are external/environmental: two sklearn tests hit Windows `PermissionError` while creating multiprocessing pipes; three TomTom tests require outbound calls refused with `WinError 10061`; one video test setup hit `WinError 5` while pytest removed the shared `.pytest-temp` directory. The route-specific response tests passed in the suite; the focused route run also passed after the final PostGIS query change.
- External OSRM/TomTom requests remain unavailable from this execution environment as described above; the route endpoint's registered PostGIS fallback is operational for matching endpoints.

## Runtime blocker

TomTom and OSRM outbound connections are refused from this execution environment. Successful live provider retrieval cannot be confirmed here. Fallback routing works for matching registered roads, and the TomTom route fallback is covered with a mocked successful HTTP response.

## Phase 9 — connectivity verification, alerts, and automation

Updated: 2026-11-10

### Connectivity and live-traffic reliability

- Repeated runtime probes with the configured TomTom key loaded (the key was not printed) showed independent Flow, Incident Details, and OSRM route requests failing with Windows `WinError 10061` connection refused. This is an outbound network/proxy/firewall restriction in this execution host, not a missing key or an observed authentication rejection. The existing TomTom v4 Flow and v5 Incident Details products remain in use; OSRM remains primary and PostGIS/TomTom routing fallbacks remain intact. No live provider success is claimed.
- TomTom now reuses a bounded `httpx.Client`, applies 2-second connect / 4-second read timeouts, retries transient connection/gateway failures once with backoff, and coalesces concurrent identical flow/incident requests. A short-TTL cache is distinguished from stale flow data; stale flow is only served for up to one hour and is labeled `STALE`. Provider errors remain visible alongside fallback data.
- Redis latest snapshots now expire after 60 seconds by default and older timestamps are rejected. Redis connection settings are environment-driven. Alert deduplication/cooldowns in Redis are advisory; database idempotency and persistence remain authoritative when Redis is unavailable.
- Live Traffic hooks pass React Query cancellation signals to Axios and use bounded request timeouts. Health diagnostics query PostgreSQL/PostGIS, Redis PING, Kafka TCP, and alert tables without issuing paid TomTom requests. Provider and OSRM status reflects their last real request.
- Route alternative probing is now limited to four OSRM via candidates and runs only when OSRM supplied the primary geometry. A PostGIS/TomTom fallback route no longer triggers an additional series of OSRM calls during a primary provider outage.

### Alert implementation

- Added persistent `alert_rules`, `traffic_alerts`, and `alert_notifications` models. `create_all`/the existing migration helper creates missing tables additively; default rules seed only when absent, preserving operator configuration.
- Added configurable rules for high/critical congestion, speed reduction, traffic delay, incident categories, road closures, roadworks, stationary traffic, AI high-congestion forecasts, and traffic anomalies. Threshold updates are checked against supported rule keys, types, finiteness, and ranges.
- Alert events retain source, source event ID, original timestamp, road/intersection and location, route reference, and input metadata. Event IDs, active scope deduplication and cooldowns prevent repeated alerts; notifications are created with new persisted alerts. APIs support rules, active alerts, resolved history, route corridor matching, acknowledge/resolve, read notifications, and statistics.
- Kafka processing validates payloads, uses topic/partition/offset identities, commits poison messages after logging, retries transient database failures, and writes PostgreSQL before best-effort Redis state. Video observations are route-associated only when registered camera/intersection coordinates are available. TomTom incidents/flow and fresh AI results enter the same rule engine.
- The existing dashboard now has Alerts tabs for active alerts, history, notifications, and rule controls, plus unread notification access in the top bar. Route searches use PostGIS `ST_DWithin` and report distance along the route when available.

### Verification

- Phase 9 focused backend tests: **9 passed** (TomTom bounded retry/cache, concurrent request coalescing, incident parsing, Redis TTL/freshness/keys, health diagnostics, alert generation/deduplication, route spatial matching, lifecycle, notifications, Kafka validation, and rules).
- Existing API endpoint tests: **8 passed**, including the fractional `direction_counts.length_meters` regression and prediction/history endpoints.
- Frontend ESLint: **passed**. Vite production build: **passed**; Vite reports the existing large JavaScript chunk (>500 kB).
- Full backend suite collected **93 tests**. The run passed through 33 tests and then remained in `test_route_corridor_retrieves_registered_arterials`, which exercises external OSRM/TomTom corridor retrieval; it was stopped without a final suite result. The route alternative probe was bounded afterward, but a rerun of this network-dependent route test still did not finish within the verification window. Earlier Phase 8 suite results in this file also include environment failures (Windows multiprocessing permissions, refused external network, and shared pytest temp cleanup). The complete regression suite is therefore **not verified** in this run.
- Direct provider checks remain blocked by outbound connection refusal. Mocked request tests verify request construction, retry, caching, and parsing; these do not establish live TomTom/OSRM connectivity.

### Remaining limitations

- Live TomTom Flow, TomTom incidents, and external OSRM cannot be confirmed from this host until outbound connectivity is restored. Local PostGIS routes and application fallback behavior remain available for matching registered roads.
- The 93-test suite needs a complete rerun in an environment where route integration requests terminate within their configured bounds; this run ended during the live corridor test and must not be presented as a pass.
- Phase 10 deployment work has not started.
