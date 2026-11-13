from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import SessionLocal
from backend.app.main import app
from backend.app.models.traffic_alert import AlertNotification, TrafficAlert
from backend.app.schemas.alerts import AlertEventInput
from vision.streaming.kafka_consumer import process_kafka_payload
from vision.streaming.redis_client import TrafficRedis


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def redis_offline(monkeypatch):
    monkeypatch.setattr(TrafficRedis, "get_alert_event", lambda *_args: None)
    monkeypatch.setattr(TrafficRedis, "get_alert_cooldown", lambda *_args: None)
    monkeypatch.setattr(TrafficRedis, "set_alert_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(TrafficRedis, "set_alert_cooldown", lambda *_args, **_kwargs: None)


def test_alert_generation_spatial_filter_lifecycle_and_notification(client, redis_offline):
    event_id = f"alert-test:{uuid4()}"
    response = client.post("/alerts/evaluate", json={
        "source": "test_traffic_sensor",
        "source_event_id": event_id,
        "timestamp": datetime.utcnow().isoformat(),
        "intersection_id": "INT_001",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "average_speed": 8,
        "free_flow_speed": 50,
        "density": 0.9,
        "congestion_level": "HIGH",
        "delay_seconds": 600,
    })
    assert response.status_code == 200, response.text
    alerts = response.json()
    assert {alert["rule_key"] for alert in alerts} >= {
        "congestion_high", "congestion_critical", "significant_speed_reduction", "traffic_delay"
    }
    assert all(alert["source"] == "test_traffic_sensor" for alert in alerts)

    duplicate = client.post("/alerts/evaluate", json={
        "source": "test_traffic_sensor",
        "source_event_id": event_id,
        "timestamp": datetime.utcnow().isoformat(),
        "latitude": 13.0827,
        "longitude": 80.2707,
        "average_speed": 8,
        "free_flow_speed": 50,
        "density": 0.9,
        "congestion_level": "HIGH",
        "delay_seconds": 600,
    })
    assert duplicate.status_code == 200
    assert {alert["id"] for alert in duplicate.json()} == {alert["id"] for alert in alerts}

    route = client.post("/alerts/route", json={
        "route_id": "route-alert-test",
        "geometry": {"type": "LineString", "coordinates": [[80.269, 13.0827], [80.273, 13.0827]]},
        "corridor_meters": 350,
    })
    assert route.status_code == 200, route.text
    route_alerts = route.json()
    assert {item["alert"]["id"] for item in route_alerts} == {alert["id"] for alert in alerts}
    assert all(item["distance_to_route_meters"] < 350 for item in route_alerts)
    assert all(item["distance_along_route_meters"] is not None for item in route_alerts)

    target_id = alerts[0]["id"]
    acknowledged = client.post(f"/alerts/{target_id}/acknowledge")
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "ACKNOWLEDGED"
    resolved = client.post(f"/alerts/{target_id}/resolve")
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "RESOLVED"

    history = client.get("/alerts/history")
    assert history.status_code == 200
    assert any(item["id"] == target_id and item["status"] == "RESOLVED" for item in history.json())
    notifications = client.get("/alerts/notifications")
    assert notifications.status_code == 200
    assert notifications.json()["unread_count"] >= len(alerts)
    notification_id = notifications.json()["notifications"][0]["id"]
    marked = client.post(f"/alerts/notifications/{notification_id}/read")
    assert marked.status_code == 200 and marked.json()["is_read"] is True
    assert client.get("/alerts/statistics").status_code == 200

    with SessionLocal() as db:
        ids = [item["id"] for item in alerts]
        db.query(AlertNotification).filter(AlertNotification.alert_id.in_(ids)).delete(synchronize_session=False)
        db.query(TrafficAlert).filter(TrafficAlert.id.in_(ids)).delete(synchronize_session=False)
        db.commit()


def test_alert_input_rejects_future_timestamps_and_unpaired_coordinates():
    with pytest.raises(ValueError, match="future"):
        AlertEventInput.model_validate({
            "source": "sensor",
            "timestamp": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        })
    with pytest.raises(ValueError, match="provided together"):
        AlertEventInput.model_validate({"source": "sensor", "latitude": 13.0})


def test_kafka_payload_validation_dedup_and_redis_fallback():
    class FakeRedis:
        def __init__(self):
            self.events = set()
            self.snapshots = []

        def get_alert_event(self, event_id):
            return event_id in self.events

        def set_alert_event(self, event_id, ttl_seconds):
            self.events.add(event_id)

        def set_latest(self, payload):
            self.snapshots.append(payload)

    fake_redis = FakeRedis()
    calls = []

    def storage(payload, source_event_id):
        calls.append((payload, source_event_id))
        return SimpleNamespace(timestamp=payload["timestamp"])

    payload = {
        "source": "video_analysis",
        "timestamp": datetime.utcnow().isoformat(),
        "camera_id": "CAM_001",
        "total_vehicles": 10,
        "average_speed": 18,
        "density": 0.5,
        "congestion_level": "MEDIUM",
        "anomaly_detected": True,
    }
    first = process_kafka_payload(payload, "routex-traffic-events:0:42", redis_client=fake_redis, storage=storage)
    duplicate = process_kafka_payload(payload, "routex-traffic-events:0:42", redis_client=fake_redis, storage=storage)
    assert first is not None and duplicate is None
    assert len(calls) == 1
    assert len(fake_redis.snapshots) == 1


def test_alert_rules_can_be_configured(client):
    rules = client.get("/alert-rules")
    assert rules.status_code == 200
    rule = next(item for item in rules.json() if item["rule_key"] == "traffic_delay")
    original = {key: rule[key] for key in ("enabled", "severity", "cooldown_seconds", "thresholds")}
    updated = client.patch("/alert-rules/traffic_delay", json={"severity": "HIGH", "cooldown_seconds": 60})
    assert updated.status_code == 200
    assert updated.json()["severity"] == "HIGH"
    restored = client.patch("/alert-rules/traffic_delay", json=original)
    assert restored.status_code == 200
    invalid_threshold = client.patch("/alert-rules/traffic_delay", json={"thresholds": {"minimum_delay_seconds": -1}})
    assert invalid_threshold.status_code == 422
