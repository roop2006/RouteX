import pytest
from fastapi.testclient import TestClient
from backend.app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_registered_routes_exist():
    route_paths = [r.path for r in app.routes if hasattr(r, "path")]
    openapi_paths = list(app.openapi()["paths"].keys())

    expected_routes = [
        "/live-traffic/",
        "/geo/nearby-events",
        "/geo/zones",
        "/intersections/",
        "/roads/",
        "/prediction/",
        "/ai/live-prediction",
        "/analysis/route",
        "/analysis/video/upload",
        "/analysis/video/sample",
        "/analysis/geocoding/search",
        "/analysis/combine",
    ]

    for expected in expected_routes:
        assert expected in openapi_paths, f"Route {expected} must be registered in FastAPI app"


def test_intersections_endpoint(client):
    response = client.get("/intersections/")
    # If DB is running, should return 200 with list
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_roads_endpoint(client):
    response = client.get("/roads/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_geo_zones_endpoint(client):
    response = client.get("/geo/zones")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_geo_nearby_events_endpoint(client):
    response = client.get("/geo/nearby-events?latitude=12.9716&longitude=77.5946&radius_meters=500")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_live_traffic_endpoint_graceful_handling_without_redis(client, monkeypatch):
    # Mock redis get_latest to return simulated live traffic data
    from vision.streaming.redis_client import TrafficRedis
    monkeypatch.setattr(TrafficRedis, "get_latest", lambda self: {
        "timestamp": "2026-10-21T12:00:00",
        "total_vehicles": 22,
        "average_speed": 38.5,
        "density": 0.44
    })
    response = client.get("/live-traffic/")
    assert response.status_code == 200
    assert response.json()["total_vehicles"] == 22


def test_ai_live_prediction_endpoint_with_mocked_redis(client, monkeypatch):
    from vision.streaming.redis_client import TrafficRedis
    monkeypatch.setattr(TrafficRedis, "get_latest", lambda self: {
        "timestamp": "2026-10-21T12:00:00",
        "total_vehicles": 18,
        "average_speed": 42.0,
        "density": 0.35
    })
    response = client.get("/ai/live-prediction/")
    assert response.status_code == 200
    data = response.json()
    assert "traffic_data" in data
    assert "prediction" in data
    assert data["prediction"]["predicted_congestion"] in ["LOW", "MEDIUM", "HIGH"]
