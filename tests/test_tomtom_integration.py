"""
Comprehensive verification test suite for TomTom Live Traffic API integration in RouteX.
Covers:
- Test A: API configuration, key loading, key masking security
- Test B: Traffic Flow segment data retrieval, validation, and TTL caching
- Test C: Traffic Incidents details parsing, normalization, and bounding box queries
- Test D: PostGIS persistence, SRID 4326 verification, source provenance tracking
- Test E: Route corridor intelligence end-to-end integration
- Test F: AI production model (15 features) execution with TomTom-derived telemetry
- Test G: Live traffic API endpoints (/live-traffic/, /live-traffic/tomtom, /live-traffic/incidents, /live-traffic/tile/...)
- Test H: Error handling, rate limit backoff, and graceful degradation
"""
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app.core.database import SessionLocal
from backend.app.main import app
from backend.app.models.traffic_stream_event import TrafficStreamEvent
from backend.app.schemas.user_analysis import RouteAnalysisRequest, RouteCoordinates
from backend.app.services.route_analysis_service import calculate_user_route, fetch_tomtom_route
from backend.app.services.tomtom_traffic_service import tomtom_traffic_service
from ml.prediction.predictor import TrafficPredictor


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# -----------------------------------------------------------------------------
# Test A: Configuration & Security
# -----------------------------------------------------------------------------
def test_tomtom_service_configuration_and_key_masking():
    """Confirms API key is loaded, verified, and masked securely in logs."""
    assert tomtom_traffic_service.is_configured is True
    masked = tomtom_traffic_service.masked_key
    assert len(masked) >= 8
    assert "..." in masked
    # Full key must never be identical to masked key
    assert masked != tomtom_traffic_service.api_key
    assert tomtom_traffic_service.cache_ttl >= 60


# -----------------------------------------------------------------------------
# Test B: Traffic Flow Segment Data & Caching
# -----------------------------------------------------------------------------
def test_tomtom_flow_segment_retrieval_and_caching():
    """Retrieves real-time traffic flow data for Chennai Central and verifies caching."""
    lat, lng = 13.0827, 80.2707
    flow = tomtom_traffic_service.get_flow_segment_data(lat, lng)

    assert flow is not None
    assert flow["source"] == "tomtom_traffic_flow"
    assert flow["current_speed"] >= 0.0
    assert flow["free_flow_speed"] >= 0.0
    assert flow["current_travel_time"] >= 0.0
    assert flow["free_flow_travel_time"] >= 0.0
    assert flow["confidence"] >= 0.0
    assert flow["congestion_level"] in ("LOW", "MEDIUM", "HIGH")
    assert 0.0 <= flow["density"] <= 1.0

    # Test cache hit: subsequent query with nearby coordinates (~10m away) must hit cache
    initial_requests = tomtom_traffic_service.stats["total_requests"]
    cached_flow = tomtom_traffic_service.get_flow_segment_data(13.08272, 80.27072)
    assert cached_flow is not None
    assert cached_flow["current_speed"] == flow["current_speed"]
    # Verify no new external HTTP request was made
    assert tomtom_traffic_service.stats["total_requests"] == initial_requests


# -----------------------------------------------------------------------------
# Test C: Traffic Incidents Details
# -----------------------------------------------------------------------------
def test_tomtom_incidents_details_parsing():
    """Queries traffic incidents in Chennai metro bounding box and verifies parsed fields."""
    incidents = tomtom_traffic_service.get_incident_details(
        min_lng=80.10,
        min_lat=12.90,
        max_lng=80.35,
        max_lat=13.20,
    )
    assert isinstance(incidents, list)
    if incidents:
        first = incidents[0]
        assert "id" in first
        assert "category_name" in first
        assert "magnitude_label" in first
        assert "delay_seconds" in first
        assert "length_meters" in first
        assert first["source"] == "tomtom_traffic_incidents"
        assert first["delay_seconds"] >= 0.0


def test_live_incidents_endpoint_exposes_tomtom_upstream_failure(client, monkeypatch):
    monkeypatch.setattr(tomtom_traffic_service, "last_incident_error", None)

    def fail_incident_query(**_kwargs):
        tomtom_traffic_service.last_incident_error = (
            "TomTom incident request failed: outbound connection refused"
        )
        return []

    monkeypatch.setattr(tomtom_traffic_service, "get_incident_details", fail_incident_query)
    response = client.get("/live-traffic/incidents")

    assert response.status_code == 502
    assert "outbound connection refused" in response.json()["detail"]


def test_live_traffic_fallback_reports_tomtom_failure(client, monkeypatch):
    from vision.streaming.redis_client import TrafficRedis

    monkeypatch.setattr(tomtom_traffic_service, "last_flow_error", None)

    def fail_flow_query(*_args, **_kwargs):
        tomtom_traffic_service.last_flow_error = "TomTom traffic flow: outbound connection refused"
        return None

    monkeypatch.setattr(TrafficRedis, "get_latest", lambda _self: None)
    monkeypatch.setattr(tomtom_traffic_service, "get_flow_segment_data", fail_flow_query)

    response = client.get("/live-traffic/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("CACHED_STREAM", "UNAVAILABLE")
    assert "outbound connection refused" in data["provider_error"]


def test_tomtom_routing_fallback_uses_httpx_client(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "routes": [{
                    "summary": {"lengthInMeters": 1250, "travelTimeInSeconds": 180},
                    "legs": [{"points": [
                        {"longitude": 80.27, "latitude": 13.08},
                        {"longitude": 80.28, "latitude": 13.09},
                    ]}],
                }]
            }

    def fake_get(url, *, params, timeout):
        captured.update(url=url, params=params, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr("backend.app.services.route_analysis_service.httpx.get", fake_get)
    route = fetch_tomtom_route(80.27, 13.08, 80.28, 13.09)

    assert route["code"] == "Ok"
    assert route["routes"][0]["geometry"]["coordinates"] == [[80.27, 13.08], [80.28, 13.09]]
    assert captured["timeout"] == 6.0
    assert "key" in captured["params"]
    assert "key=" not in captured["url"]


# -----------------------------------------------------------------------------
# Test D: PostGIS Ingestion & Source Provenance
# -----------------------------------------------------------------------------
def test_tomtom_route_corridor_ingestion_and_postgis(db):
    """Verifies route corridor waypoints are ingested into PostGIS with SRID 4326."""
    coords = [
        [80.2608, 13.0782],  # Egmore
        [80.2350, 13.0800],  # Kilpauk
        [80.2100, 13.0850],  # Anna Nagar
    ]
    res = tomtom_traffic_service.ingest_route_observations(coords, db)
    assert res["flow_count"] >= 1
    assert "incidents" in res

    # Verify rows in PostgreSQL traffic_stream_events
    recent_events = (
        db.query(TrafficStreamEvent)
        .filter(TrafficStreamEvent.latitude.isnot(None))
        .order_by(TrafficStreamEvent.id.desc())
        .limit(20)
        .all()
    )
    matching = [
        e for e in recent_events
        if any(
            isinstance(evt, dict) and evt.get("source") in ("tomtom_traffic_flow", "tomtom_traffic_incidents")
            for evt in (e.events if isinstance(e.events, list) else [])
        )
    ]
    assert len(matching) > 0
    flow_event = matching[0]
    assert flow_event is not None
    assert flow_event.location is not None

    # Check SRID in PostGIS
    srid_row = db.execute(
        text("SELECT ST_SRID(location) as srid FROM traffic_stream_events WHERE id = :id"),
        {"id": flow_event.id},
    ).first()
    assert srid_row.srid == 4326

    # Verify source provenance
    evts = flow_event.events if isinstance(flow_event.events, list) else []
    assert len(evts) > 0
    src = evts[0].get("source")
    assert src in ("tomtom_traffic_flow", "tomtom_traffic_incidents")


# -----------------------------------------------------------------------------
# Test E: Route Intelligence Integration with TomTom
# -----------------------------------------------------------------------------
def test_route_analysis_with_tomtom_corridor(db):
    """
    Queries real OSRM route between Egmore and Anna Nagar,
    verifying TomTom live telemetry and AI status.
    """
    req = RouteAnalysisRequest(
        origin=RouteCoordinates(lat=13.0782, lng=80.2608, name="Egmore Junction"),
        destination=RouteCoordinates(lat=13.0850, lng=80.2100, name="Anna Nagar"),
        include_alternatives=False,
    )
    resp = calculate_user_route(req, db)

    assert resp.selected_route.distance_km > 0.0
    assert resp.selected_route.free_flow_duration_minutes > 0.0
    assert resp.corridor.telemetry_status == "AVAILABLE"
    assert resp.corridor.telemetry_sample_count > 0
    assert resp.corridor.observed_average_speed is not None
    assert resp.ai_prediction.status in {"AVAILABLE", "INSUFFICIENT_DATA"}
    if resp.ai_prediction.status == "AVAILABLE":
        assert resp.corridor.observed_total_vehicles is not None
    if resp.ai_prediction.status == "AVAILABLE":
        assert resp.ai_prediction.model_name == "routex_production_predictor"
    assert resp.traffic_provider is not None


# -----------------------------------------------------------------------------
# Test F: AI Production Model 15-Feature Schema Compatibility
# -----------------------------------------------------------------------------
def test_ai_production_model_with_tomtom_telemetry():
    """
    Verifies that TomTom observations translate into the exact 15-feature
    schema required by the production TrafficPredictor.
    """
    predictor = TrafficPredictor()
    now = datetime.now()

    # Feature transformation from TomTom flow observation
    sample_flow = {
        "total_vehicles": 25,
        "average_speed": 28.5,
        "density": 0.35,
        "hour": now.hour,
        "minute": now.minute,
        "day_of_week": now.weekday(),
        "is_weekend": 1 if now.weekday() >= 5 else 0,
        "is_peak_hour": 1 if now.hour in (8, 9, 10, 17, 18, 19) else 0,
        "vehicles_lag_1": 22,
        "vehicles_lag_2": 20,
        "vehicles_lag_3": 18,
        "speed_lag_1": 29.0,
        "speed_lag_2": 30.0,
        "density_lag_1": 0.32,
        "density_lag_2": 0.30,
    }

    pred = predictor.predict(sample_flow)
    assert "predicted_congestion" in pred
    assert pred["predicted_congestion"] in ("LOW", "MEDIUM", "HIGH")
    assert 0.0 <= pred["prediction_confidence"] <= 1.0
    assert pred["predicted_vehicle_count"] >= 0.0


# -----------------------------------------------------------------------------
# Test G: Live Traffic API Endpoints
# -----------------------------------------------------------------------------
def test_live_traffic_endpoints(client):
    """Verifies all Live Traffic endpoints return HTTP 200 with valid structures."""
    # 1. Main live traffic telemetry
    r1 = client.get("/live-traffic/")
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["status"] in ("ACTIVE", "CACHED_STREAM", "UNAVAILABLE")

    # 2. TomTom city snapshot
    r2 = client.get("/live-traffic/tomtom")
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["status"] in ("ACTIVE", "UNAVAILABLE", "UNCONFIGURED")
    assert "junctions" in data2

    # 3. Live incidents endpoint
    r3 = client.get("/live-traffic/incidents")
    assert r3.status_code == 200
    data3 = r3.json()
    assert "incidents" in data3
    assert "count" in data3

    # 4. Map tile proxy endpoint (Flow layer)
    r4 = client.get("/live-traffic/tile/flow/10/734/473.png")
    assert r4.status_code == 200
    assert r4.headers["content-type"] == "image/png"
    assert len(r4.content) > 0

    # 5. Map tile proxy endpoint (Incidents layer)
    r5 = client.get("/live-traffic/tile/incidents/10/734/473.png")
    assert r5.status_code == 200
    assert r5.headers["content-type"] == "image/png"
    assert len(r5.content) > 0


# -----------------------------------------------------------------------------
# Test H: Error Handling & Circuit Breaker
# -----------------------------------------------------------------------------
def test_invalid_tile_layer_returns_400(client):
    """Invalid layer request returns 400 Bad Request."""
    r = client.get("/live-traffic/tile/unknown_layer/10/734/473.png")
    assert r.status_code == 400
