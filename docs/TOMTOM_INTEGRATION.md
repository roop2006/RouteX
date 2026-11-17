# RouteX — TomTom Traffic API Integration Architecture & Guide

Updated 2026-11-15: the [Phase 9 repair report](PHASE9_INTEGRATION_REPORT.md) supersedes older verification notes below. Real Flow, Incidents and OSRM calls succeeded with network access outside the sandbox. Provider vehicle counts remain unavailable; no synthetic counts are supplied to the production predictor. Route alerts share the selected geometry and full-geometry PostGIS matching with the map.

## 1. Executive Overview

RouteX integrates the TomTom Traffic API as a production-grade external real-time data source. The integration provides:
- Genuine road-level traffic flow speeds, free-flow speeds, travel times, and congestion factors.
- Real-time traffic incident reports (stationary traffic, accidents, lane closures, roadworks) with precise bounding box spatial filtering.
- Route-aware corridor telemetry extraction along OSRM road geometry.
- Automated observation persistence into PostgreSQL / PostGIS with strict data provenance (`tomtom_traffic_flow` and `tomtom_traffic_incidents`).
- Existing 15-feature production predictor preserved; inference requires measured vehicle counts, speed and density from a suitable observation source.
- Multi-tier live traffic telemetry retrieval with Redis buffer caching, TomTom live queries, and graceful standby states.
- Secure, credential-masked proxying of TomTom map tiles to the frontend Leaflet map without exposing the API key.

---

## 2. Enabled TomTom Products & Endpoints

| Product | Endpoint URL | Format | Usage in RouteX |
| :--- | :--- | :--- | :--- |
| **Traffic Flow API (v4)** | `https://api.tomtom.com/traffic/services/4/flowSegmentData/{style}/{zoom}/json?point={lat},{lng}&key={key}` | JSON | Segment speed, free-flow velocity, travel time, confidence, FRC, coordinates |
| **Traffic Incidents API (v5)** | `https://api.tomtom.com/traffic/services/5/incidentDetails?bbox={minLng},{minLat},{maxLng},{maxLat}&fields={...}&key={key}` | JSON | Incident IDs, category, delay seconds, affected road, start/end time, LineString geometry |
| **Orbis Traffic Flow Vector Tiles (v2)** | `https://api.tomtom.com/maps/orbis/traffic/flow/vector/tile/{z}/{x}/{y}?apiVersion=2&key={key}` | MVT / PBF | High-efficiency vector tiles for large area flow rendering |
| **Orbis Traffic Incidents Vector Tiles (v1)** | `https://api.tomtom.com/maps/orbis/traffic/tile/incidents/{z}/{x}/{y}.pbf?apiVersion=1&key={key}` | PBF | High-efficiency vector tiles for incident clustering |
| **Traffic Map Raster Tiles (v4)** | `https://api.tomtom.com/traffic/map/4/tile/flow/{style}/{z}/{x}/{y}.png?key={key}` | PNG | Proxied raster overlay tiles for Leaflet map integration |
| **Traffic Incident Raster Tiles (v4)** | `https://api.tomtom.com/traffic/map/4/tile/incidents/s0/{z}/{x}/{y}.png?key={key}` | PNG | Proxied incident icon tiles for Leaflet map integration |

---

## 3. Environment Variables & Security

* **Variable**: `TOMTOM_API_KEY` (configured in `.env`).
* **Security Rules**:
  - The API key is loaded only in the backend via `pydantic_settings.BaseSettings` in `backend/app/core/config.py`.
  - The API key is **never** sent to React or returned in API responses.
  - Diagnostic logs print only a masked representation (e.g. `NQEH...cNgh`).
  - Tile requests from the frontend are routed through backend proxy endpoints (`/live-traffic/tile/{layer}/{z}/{x}/{y}.png`), ensuring client browsers never obtain the key.

---

## 4. Quota Management & Caching Architecture

To prevent wasting the user's free tier allowance (500 requests/day for Orbis Extended Tiles; standard Traffic API quotas):

1. **Coordinate Grid Rounding**:
   - Point queries for `flowSegmentData` round latitude and longitude to 3 decimal places (~110m). Any queries within ~110m reuse the cached segment.
   - Bounding box queries for `incidentDetails` round coordinates to 2 decimal places (~1km grid).
2. **TTL In-Memory Cache**:
   - `flowSegmentData`: 300 seconds (5 minutes) TTL.
   - `incidentDetails`: 600 seconds (10 minutes) TTL.
   - Map tiles: 300 seconds (5 minutes) TTL.
3. **Route Waypoint Sampling**:
   - For an entire route spanning multiple kilometers, RouteX samples 2 to 4 representative waypoints along the road geometry rather than polling every point, consuming at most 2–4 flow requests and 1 incident request per unique route corridor.
4. **Circuit Breaker / Backoff**:
   - If HTTP 429 ("Too Many Requests") is received, external calls are automatically paused for 60 seconds, returning cached or database fallback telemetry.

---

## 5. PostGIS Data Ingestion & Provenance

When TomTom observations are retrieved along a route corridor or for live monitoring, they are persisted into PostgreSQL `traffic_stream_events`:

* **Table**: `traffic_stream_events`
* **SRID**: `4326` (WGS 84 Point Geometry)
* **Columns**:
  - `total_vehicles`: `null` because this provider does not report vehicle counts. Incident-only observations also have null speed and density.
  - `average_speed`: TomTom `currentSpeed` (km/h)
  - `density`: `max(0.0, min(1.0, 1.0 - currentSpeed / freeFlowSpeed))`
  - `congestion_level`: `"LOW"`, `"MEDIUM"`, or `"HIGH"`
  - `latitude`, `longitude`, `location` (`ST_SetSRID(ST_MakePoint(lng, lat), 4326)`)
  - `events`: JSON metadata preserving provider, FRC, delay, free-flow metrics, and source:
    - `"source": "tomtom_traffic_flow"`
    - `"source": "tomtom_traffic_incidents"`
* **Deduplication**: Lookups within 150m in the last 5 minutes suppress redundant DB inserts.

---

## 6. End-to-End AI Model Integration

RouteX maintains strict separation across prediction models:
1. **Production Predictor (`TrafficPredictor`)**: Requires exactly 15 features:
   - 8 Base features: `total_vehicles`, `average_speed`, `density`, `hour`, `minute`, `day_of_week`, `is_weekend`, `is_peak_hour`.
   - 7 Lag & rolling features: `vehicles_lag_1`, `vehicles_lag_2`, `vehicles_lag_3`, `speed_lag_1`, `speed_lag_2`, `density_lag_1`, `density_lag_2`.
   - TomTom-only observations cannot satisfy the measured vehicle-count requirement. Route prediction reports `INSUFFICIENT_DATA` until suitable measured observations exist; invented counts and legacy synthetic benchmark observations are excluded.
2. **External Predictor (`ExternalTrafficPredictor`)**: Trained on the Metro Interstate Traffic Volume dataset (Minneapolis). Strictly uses a 9-feature schema and is never applied to Chennai urban route corridors.

---

## 7. Historical Verification Results (superseded by the repair report)

All 81 backend tests pass (100% pass rate):
- `tests/test_tomtom_integration.py`: 8 tests passed
- `tests/test_live_traffic_and_ingestion.py`: 8 tests passed
- `tests/test_user_analysis_workflow.py`: 18 tests passed
- Full regression suite across Phase 1–8: 81 passed in 107.66s
- Frontend lint: 0 errors, 0 warnings
- Frontend build: 2,695 client modules built cleanly in 1.44s

## 8. Selected Route Dashboard Integration (Phase 8)

`SelectedRouteProvider` shares the route analysis, selected alternative, origin and destination, stable route ID, geometry, distance, estimated duration, and calculation time across the dashboard. Editing either route endpoint clears the selected route and its derived route/video analysis results until a new route calculation succeeds. Selecting an alternative updates the shared route without recalculating it.

`POST /analysis/route` evaluates each returned route geometry against the existing PostGIS tables. Roads use a 250 m corridor and are labeled `INTERSECTS` or `NEARBY`; intersections and stored traffic observations use a 350 m corridor. Road/intersection observation summaries associate events within 100 m of the asset. Traffic observations include their source and provider metadata, location, time, event details, and available vehicle/current-speed/free-flow-speed/density values. Freshness is reported as `FRESH` (up to 5 minutes), `RECENT` (up to 1 hour), `HISTORICAL`, or `UNAVAILABLE`. No route data is synthesized when the corridor has no observations.

The route response retains the existing endpoint and adds per-alternative `route_id`, corridor details, and AI result. Traffic Analysis consumes the selected corridor observations; Roads and Intersections render only the selected alternative's matched assets. With no selected route, these pages retain their existing general database views. Route AI uses the existing production predictor only when corridor flow observations are available. Video-derived results remain separate unless the existing combined-analysis association check confirms a camera/intersection association.

Route matching uses SRID 4326 geometries and geography distance predicates in metres. The envelope prefilter can use the existing geometry GiST index; exact membership uses `ST_DWithin`, and road intersection status uses `ST_Intersects`. The frontend does not poll duplicate route endpoints: route-specific records are part of the route-analysis response.

Focused regression coverage now checks route identifiers, per-alternative corridor/AI payloads, road geometry and match relation, valid observation locations/source, and freshness fields. See `progress.md` for the current verification results and documentation files that are absent from this checkout.

## 9. Phase 9 connectivity status and alert integration

The TomTom service continues to use the existing Traffic Flow v4 and Incident Details v5 products. The service now uses a shared bounded `httpx.Client` (2-second connect and 4-second read timeouts), a single retry for transient network/gateway errors, and per-query singleflight so simultaneous requests for the same cache key share one provider request. Flow responses are marked cached or stale; stale flow is limited to one hour. Incidents are cached separately. Credentials remain server-side and are never included in client responses or logs.

Direct Flow and Incident Details calls were checked independently in this environment. Both returned Windows `WinError 10061` (connection refused); OSRM did as well. The configured key loaded, but live data could not be verified because outbound connections from the host were refused. This is not evidence of a provider authentication failure. Health diagnostics report the last real provider observation without triggering a paid request. Mocked tests cover request construction, retries, caching, concurrency coalescing, incident parsing, and graceful errors, but do not claim external connectivity.

Persisted flow/incident observations, Kafka traffic messages, verified video observations, and fresh existing AI predictions feed the shared configurable alert engine. Alert rules, lifecycle records, and in-app notifications are stored in PostgreSQL. Redis TTL keys accelerate deduplication and cooldown checks but are not required for persistence. Route-specific active alerts are matched against the selected route's GeoJSON LineString with PostGIS geography distance and include distance along the route where available. The alert API and dashboard expose active alerts, resolved history, notification read state, rule settings, route matching, acknowledge/resolve, and statistics. See `progress.md` for schema, test outcomes, and the full-suite limitation.
