"""Route/provider fixtures exercise real PostGIS and persistence in a rolled-back transaction."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.database import engine, get_db
from backend.app.main import app
from backend.app.models.traffic_alert import AlertNotification, TrafficAlert
from backend.app.models.traffic_stream_event import TrafficStreamEvent
from backend.app.services.alert_service import process_alert_event, route_alert_matches
from backend.app.services.tomtom_traffic_service import TomTomTrafficService, tomtom_traffic_service
from backend.app.services.route_analysis_service import evaluate_corridor_telemetry, predict_route_corridor
from vision.streaming.redis_client import TrafficRedis


@pytest.fixture
def isolated(monkeypatch):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    app.dependency_overrides[get_db] = lambda: session
    for method in ("get_alert_event", "get_alert_cooldown", "set_alert_event", "set_alert_cooldown"):
        monkeypatch.setattr(TrafficRedis, method, lambda *a, **k: None)
    try:
        with TestClient(app) as client:
            yield client, session
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def incident():
    return {
        "id": f"fixture-{uuid4()}", "icon_category": 8, "category_name": "Road Closed",
        "description": "Fixture closure", "magnitude_of_delay": 4, "delay_seconds": 0,
        "from_road": "Fixture road", "time_validity": "present", "road_numbers": ["T1"],
        "geometry": {"type": "LineString", "coordinates": [[0, 0], [0.02, 0]]},
        "centroid_lat": 0, "centroid_lng": 0.02,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


ROUTE = {"route_id": "fixture-route-a", "geometry": {"type": "LineString", "coordinates": [[0, -0.002], [0, 0.002]]}}


def test_route_incidents_update_dedup_geometry_change_and_failure(isolated, incident, monkeypatch):
    client, db = isolated
    snapshot = {"status": "AVAILABLE", "incidents": [incident], "error": None, "checked_at": incident["retrieved_at"]}
    monkeypatch.setattr(tomtom_traffic_service, "get_incident_snapshot", lambda *a: deepcopy(snapshot))
    response = client.post("/alerts/route/snapshot", json=ROUTE)
    assert response.status_code == 200, response.text
    first = response.json()
    assert first["incident_count"] == 1
    match = next(item for item in first["alerts"] if item["alert"]["source_event_id"] == incident["id"])
    assert match["distance_to_route_meters"] == 0  # Centroid is >2 km away; full line intersects.
    assert abs(match["marker_longitude"]) < 0.001
    assert match["route_id"] == ROUTE["route_id"]
    assert match["alert"]["severity"] == "CRITICAL"
    alert_id = match["alert"]["id"]

    snapshot["incidents"][0]["description"] = "Fixture closure updated"
    updated = client.post("/alerts/route/snapshot", json=ROUTE).json()
    assert next(a["alert"] for a in updated["alerts"] if a["alert"]["id"] == alert_id)["description"] == "Fixture closure updated"
    assert db.query(AlertNotification).filter_by(alert_id=alert_id).count() == 1
    assert db.query(TrafficAlert).filter_by(source_event_id=incident["id"]).count() == 1

    changed_route = {"route_id": "fixture-route-b", "geometry": {"type": "LineString", "coordinates": [[1, 1], [1.01, 1]]}}
    changed = client.post("/alerts/route/snapshot", json=changed_route).json()
    assert changed["alerts"] == [] and changed["incident_count"] == 0

    snapshot.update(status="UNAVAILABLE", incidents=[], error="Provider timeout")
    failure = client.post("/alerts/route/snapshot", json=ROUTE).json()
    assert failure["status"] == "UNAVAILABLE"
    assert failure["error"] == "Provider timeout"
    assert db.get(TrafficAlert, alert_id).status == "ACTIVE"

    # A wider successfully queried box covers the entire stored incident.
    snapshot.update(status="AVAILABLE", incidents=[], error=None)
    wider = {**ROUTE, "geometry": {"type": "LineString", "coordinates": [[-0.01, 0], [0.03, 0]]}}
    empty = client.post("/alerts/route/snapshot", json=wider).json()
    assert empty["status"] == "AVAILABLE" and empty["incident_count"] == 0 and empty["alerts"] == []
    db.expire_all()
    assert db.get(TrafficAlert, alert_id).status == "RESOLVED"


def test_expired_incidents_and_route_bound_alerts_do_not_leak(isolated, incident, monkeypatch):
    client, db = isolated
    incident["end_time"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    monkeypatch.setattr(tomtom_traffic_service, "get_incident_snapshot", lambda *a: {
        "status": "AVAILABLE", "incidents": [incident], "error": None, "checked_at": None,
    })
    assert client.post("/alerts/route/snapshot", json=ROUTE).json()["incident_count"] == 0
    alerts = process_alert_event(db, {"source": "fixture-sensor", "source_event_id": str(uuid4()),
        "latitude": 0, "longitude": 0, "route_id": "different-route", "congestion_level": "HIGH"})
    ids = {row.id for row in route_alert_matches(db, ROUTE["route_id"], ROUTE["geometry"], 350)}
    assert not ids.intersection(a.id for a in alerts)


@pytest.mark.parametrize("coords", [[["bad", 0], [1, 1]], [[True, 0], [1, 1]], [[0, 0], [0, 0]], [[200, 0], [1, 1]]])
def test_invalid_route_geometry_is_422(isolated, coords):
    client, _ = isolated
    response = client.post("/alerts/route/snapshot", json={**ROUTE, "geometry": {"type": "LineString", "coordinates": coords}})
    assert response.status_code == 422


@pytest.mark.parametrize("payload,available", [({"incidents": []}, True), ({}, False), ({"incidents": "bad"}, False)])
def test_provider_empty_response_is_distinct_from_invalid(payload, available):
    service = TomTomTrafficService()
    service.api_key = "fixture-provider-key"
    service._http_client = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: payload))
    snapshot = service.get_incident_snapshot(0.001, 0.001, 0.009, 0.009)
    assert (snapshot["status"] == "AVAILABLE") is available


def test_provider_cache_encloses_query_and_stale_timeout_is_explicit():
    service = TomTomTrafficService()
    service.api_key = "fixture-provider-key"
    calls = []
    def get(url, params):
        calls.append(params)
        return SimpleNamespace(status_code=200, json=lambda: {"incidents": []})
    service._http_client = SimpleNamespace(get=get)
    assert service.get_incident_snapshot(0.001, 0.001, 0.009, 0.009)["status"] == "AVAILABLE"
    assert calls[0]["bbox"] == "0.0,0.0,0.01,0.01"
    key = next(iter(service._incidents_cache))
    service._incidents_cache[key] = ([], datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1))
    def timeout(*a, **k):
        raise httpx.ReadTimeout("fixture timeout")
    service._http_client.get = timeout
    stale = service.get_incident_snapshot(0.001, 0.001, 0.009, 0.009)
    assert stale["status"] == "STALE" and "timeout" in stale["error"]


def test_missing_flow_metrics_are_not_fabricated():
    service = TomTomTrafficService()
    service.api_key = "fixture-provider-key"
    service._http_client = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: {"flowSegmentData": {}}))
    assert service.get_flow_segment_data(0, 0) is None
    assert service.flow_connectivity_status == "unavailable"


def test_redis_has_no_implicit_retries_and_rejects_unstamped_data(monkeypatch):
    service = TrafficRedis()
    assert service.client.connection_pool.connection_kwargs["retry"]._retries == 0
    monkeypatch.setattr(TrafficRedis, "_unavailable_until", 0)
    monkeypatch.setattr(service.client, "get", lambda *a: '{"total_vehicles": 8}')
    assert service.get_latest() is None


def test_kafka_database_idempotency_with_redis_unavailable(isolated, monkeypatch):
    _, session = isolated
    from vision.streaming import event_storage
    monkeypatch.setattr(event_storage, "SessionLocal", lambda: Session(bind=session.get_bind(), join_transaction_mode="create_savepoint"))
    key = f"fixture-topic:0:{uuid4()}"
    payload = {"source": "fixture-camera", "timestamp": datetime.now(timezone.utc).isoformat(),
               "total_vehicles": 2, "average_speed": 25, "density": 0.1}
    first = event_storage.save_traffic_event(payload, key)
    second = event_storage.save_traffic_event(payload, key)
    assert first.id == second.id
    assert session.query(TrafficStreamEvent).filter_by(source_event_id=key).count() == 1


def test_route_prediction_rejects_tomtom_invented_counts(isolated):
    _, db = isolated
    event = SimpleNamespace(total_vehicles=25, average_speed=30, density=0.4,
                            events=[{"source": "tomtom_traffic_flow"}])
    corridor = SimpleNamespace(telemetry_status="AVAILABLE", observed_average_speed=30, observed_density=0.4)
    assert predict_route_corridor([event], corridor).status == "INSUFFICIENT_DATA"


def test_worker_without_input_is_idle(monkeypatch):
    from backend.app.services import video_analysis_service as video
    monkeypatch.setattr(video, "_jobs", {})
    assert video.worker_status()["status"] == "idle"
