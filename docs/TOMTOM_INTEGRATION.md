# RouteX — TomTom Traffic API Integration Architecture & Guide

## 1. Executive Overview

RouteX integrates the TomTom Traffic API as a production-grade external real-time data source. The integration provides:
- Genuine road-level traffic flow speeds, free-flow speeds, travel times, and congestion factors.
- Real-time traffic incident reports (stationary traffic, accidents, lane closures, roadworks) with precise bounding box spatial filtering.
- Route-aware corridor telemetry extraction along OSRM road geometry.
- Automated observation persistence into PostgreSQL / PostGIS with strict data provenance (`tomtom_traffic_flow` and `tomtom_traffic_incidents`).
- Seamless feature transformation to the 15-feature RouteX production machine learning predictor (`TrafficPredictor`).
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
  - `total_vehicles`: Estimated from density index `int(12 + (30 * density))`
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
   - TomTom observed speed and density are mapped directly into this vector.
2. **External Predictor (`ExternalTrafficPredictor`)**: Trained on the Metro Interstate Traffic Volume dataset (Minneapolis). Strictly uses a 9-feature schema and is never applied to Chennai urban route corridors.

---

## 7. Verification Results

All 81 backend tests pass (100% pass rate):
- `tests/test_tomtom_integration.py`: 8 tests passed
- `tests/test_live_traffic_and_ingestion.py`: 8 tests passed
- `tests/test_user_analysis_workflow.py`: 18 tests passed
- Full regression suite across Phase 1–8: 81 passed in 107.66s
- Frontend lint: 0 errors, 0 warnings
- Frontend build: 2,695 client modules built cleanly in 1.44s
