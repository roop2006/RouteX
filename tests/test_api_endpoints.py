import pytest
from fastapi.testclient import TestClient
from backend.app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "RouteX API is running"}


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_predict_traffic_post(client):
    payload = {
        "total_vehicles": 14,
        "average_speed": 48.0,
        "density": 0.28,
        "hour": 10,
        "day_of_week": 1,
        "minute": 15,
    }
    response = client.post("/prediction/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "input" in data
    assert "prediction" in data
    assert "timestamp" in data
    assert data["prediction"]["predicted_congestion"] in ["LOW", "MEDIUM", "HIGH"]
    assert data["prediction"]["predicted_vehicle_count"] >= 0.0


def test_predict_traffic_post_no_trailing_slash(client):
    payload = {
        "total_vehicles": 5,
        "average_speed": 55.0,
        "density": 0.1,
    }
    response = client.post("/prediction", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["prediction"]["predicted_vehicle_count"] >= 0.0


def test_predict_traffic_validation_error(client):
    # Negative vehicle count should fail validation
    payload = {
        "total_vehicles": -1,
        "average_speed": 40.0,
        "density": 0.5,
    }
    response = client.post("/prediction/", json=payload)
    assert response.status_code == 422


def test_prediction_history_and_evaluation_flow(client):
    # 1. Post a prediction
    pred_res = client.post("/prediction/", json={
        "total_vehicles": 30,
        "average_speed": 35.0,
        "density": 0.55,
        "intersection_id": "INT-FLOW-TEST"
    })
    assert pred_res.status_code == 200

    # 2. Get history
    hist_res = client.get("/prediction/history?limit=10")
    assert hist_res.status_code == 200
    records = hist_res.json()
    assert len(records) > 0

    latest = records[0]
    latest_id = latest["id"]

    # 3. Evaluate single prediction
    eval_res = client.post(f"/prediction/evaluate/{latest_id}", json={
        "actual_value": 32.0,
        "actual_congestion": "MEDIUM"
    })
    assert eval_res.status_code == 200
    eval_data = eval_res.json()
    assert eval_data["evaluation_status"] == "EVALUATED"
    assert eval_data["actual_value"] == 32.0
    assert eval_data["absolute_error"] is not None

    # 4. Check evaluation metrics
    metrics_res = client.get("/prediction/metrics")
    assert metrics_res.status_code == 200
    metrics_data = metrics_res.json()
    assert metrics_data["evaluated_count"] >= 1
    assert metrics_data["mae"] is not None


def test_model_registry_endpoint(client):
    response = client.get("/prediction/models")
    assert response.status_code == 200
    data = response.json()
    assert "production_models" in data
    assert "external_models" in data
    assert len(data["production_models"]) == 2
    assert len(data["external_models"]) == 1
    assert data["external_models"][0]["name"] == "traffic_volume_model"
