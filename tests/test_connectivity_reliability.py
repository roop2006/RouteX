from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.tomtom_traffic_service import TomTomTrafficService
from vision.streaming.redis_client import TrafficRedis


def _flow_response():
    return {
        "flowSegmentData": {
            "currentSpeed": 18,
            "freeFlowSpeed": 45,
            "currentTravelTime": 120,
            "freeFlowTravelTime": 45,
            "confidence": 0.9,
            "frc": "FRC2",
            "roadClosure": False,
        }
    }


def test_tomtom_flow_retries_transient_failure_and_reuses_ttl_cache(monkeypatch):
    service = TomTomTrafficService()
    service.api_key = "unit-test-provider-key"

    class FakeClient:
        def __init__(self):
            self.calls = 0
            self.params = None

        def get(self, url, params):
            self.calls += 1
            self.params = params
            if self.calls == 1:
                raise httpx.ConnectError("connection reset", request=httpx.Request("GET", url))
            return type("Response", (), {"status_code": 200, "json": staticmethod(_flow_response)})()

    fake = FakeClient()
    service._http_client = fake
    monkeypatch.setattr("backend.app.services.tomtom_traffic_service.time.sleep", lambda _duration: None)

    result = service.get_flow_segment_data(13.0827, 80.2707)
    assert result and result["source"] == "tomtom_traffic_flow"
    assert fake.calls == 2
    assert fake.params["point"] == "13.0827,80.2707"
    assert "unit-test-provider-key" not in service._safe_request_error("flow", RuntimeError("failed"))

    cached = service.get_flow_segment_data(13.08272, 80.27072)
    assert cached and cached["freshness"] == "CACHED"
    assert fake.calls == 2


def test_tomtom_flow_cache_stampede_uses_one_provider_call(monkeypatch):
    service = TomTomTrafficService()
    service.api_key = "unit-test-provider-key"

    class FakeClient:
        calls = 0

        def get(self, url, params):
            self.calls += 1
            import time
            time.sleep(0.1)
            return type("Response", (), {"status_code": 200, "json": staticmethod(_flow_response)})()

    fake = FakeClient()
    service._http_client = fake
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _n: service.get_flow_segment_data(13.0827, 80.2707), range(5)))
    assert fake.calls == 1
    assert all(item is not None for item in results)


def test_incident_endpoint_uses_existing_tomtom_product_and_parses_source():
    service = TomTomTrafficService()
    service.api_key = "unit-test-provider-key"

    class FakeClient:
        def __init__(self):
            self.url = None
            self.params = None

        def get(self, url, params):
            self.url = url
            self.params = params
            payload = {"incidents": [{
                "geometry": {"type": "Point", "coordinates": [80.27, 13.08]},
                "properties": {
                    "id": "incident-42",
                    "iconCategory": 8,
                    "magnitudeOfDelay": 4,
                    "events": [{"description": "Road closed"}],
                    "delay": 300,
                    "length": 125.5,
                    "from": "Test Road",
                },
            }]}
            return type("Response", (), {"status_code": 200, "json": staticmethod(lambda: payload)})()

    fake = FakeClient()
    service._http_client = fake
    incidents = service.get_incident_details(80.26, 13.07, 80.28, 13.09)
    assert len(incidents) == 1
    assert incidents[0]["source"] == "tomtom_traffic_incidents"
    assert incidents[0]["icon_category"] == 8
    assert "traffic/services/5/incidentDetails" in fake.url
    assert fake.params["timeValidityFilter"] == "present"


def test_redis_snapshot_ttl_freshness_and_alert_keys(monkeypatch):
    class FakeRedisClient:
        def __init__(self, **_kwargs):
            self.values = {}
            self.last_set = None

        def set(self, key, value, **kwargs):
            self.values[key] = value
            self.last_set = (key, kwargs)

        def get(self, key):
            return self.values.get(key)

    fake = FakeRedisClient()
    monkeypatch.setattr("vision.streaming.redis_client.redis.Redis", lambda **kwargs: fake)
    redis_client = TrafficRedis()
    redis_client.set_latest({"timestamp": datetime.now(timezone.utc).isoformat(), "total_vehicles": 3}, ttl_seconds=30)
    assert fake.last_set[1]["ex"] == 30
    snapshot = redis_client.get_latest()
    assert snapshot["freshness"] == "FRESH"

    redis_client.set_alert_event("topic:0:5", ttl_seconds=100)
    assert redis_client.get_alert_event("topic:0:5")
    assert fake.last_set[1]["ex"] == 100

    stale = {"timestamp": (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat()}
    redis_client.set_latest(stale)
    assert redis_client.get_latest() is None


def test_integration_health_reports_without_requesting_paid_providers():
    with TestClient(app) as client:
        response = client.get("/health/integrations")
    assert response.status_code == 200
    components = response.json()["components"]
    assert {"database", "redis", "kafka", "tomtom_flow", "tomtom_incidents", "osrm", "alert_store"} <= set(components)
    assert components["database"]["status"] == "healthy"
    assert components["tomtom_flow"]["status"] in {"unverified", "available", "unavailable", "unconfigured"}
