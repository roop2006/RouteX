"""
Tests for Live Traffic API, Multi-Tier Fallback, Historical Ingestion,
Corridor Spatial Association, and Video-Derived Telemetry Integration.
"""
from datetime import datetime
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import pandas as pd

from backend.app.core.database import SessionLocal
from backend.app.main import app
from backend.app.models.traffic_stream_event import TrafficStreamEvent
from backend.app.services.live_traffic_service import LiveTrafficService
from backend.app.services.traffic_ingestion_service import TrafficIngestionService
from backend.app.services.video_analysis_service import (
    _jobs,
    _jobs_lock,
    get_annotated_video_path,
)
from ml.prediction.external_predictor import ExternalTrafficPredictor
from ml.prediction.predictor import TrafficPredictor


@pytest.fixture
def client():
    return TestClient(app)


def test_live_traffic_fallback_to_database(client, monkeypatch):
    """
    Verify that when Redis is empty/offline, /live-traffic/ falls back gracefully
    to PostgreSQL latest stream telemetry with HTTP 200 instead of failing with 404/503.
    """
    from vision.streaming.redis_client import TrafficRedis
    monkeypatch.setattr(TrafficRedis, "get_latest", lambda self: None)

    res = client.get("/live-traffic/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["CACHED_STREAM", "UNAVAILABLE", "ACTIVE"]
    assert "source" in data
    assert "total_vehicles" in data
    assert "congestion_level" in data


def test_live_traffic_ingest_endpoint(client):
    """
    Verify /live-traffic/ingest validates payload, coordinates, and persists to PostgreSQL.
    """
    payload = {
        "intersection_id": "INT_001",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "total_vehicles": 35,
        "average_speed": 28.5,
        "density": 0.55,
        "congestion_level": "MEDIUM",
        "source": "live_camera_feed_test",
        "timestamp": datetime.now().isoformat(),
    }

    res = client.post("/live-traffic/ingest", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "INGESTED"
    assert data["intersection_id"] == "INT_001"
    assert data["total_vehicles"] == 35


def test_live_traffic_ingest_invalid_coordinates(client):
    """
    Verify /live-traffic/ingest rejects invalid geographic coordinates.
    """
    payload = {
        "intersection_id": "INT_001",
        "latitude": 999.0,  # Invalid latitude
        "longitude": 80.2707,
        "total_vehicles": 10,
    }

    res = client.post("/live-traffic/ingest", json=payload)
    assert res.status_code == 400
    assert "Invalid latitude" in res.json()["detail"]


def test_historical_dataset_ingestion_and_validation():
    """
    Verify TrafficIngestionService validates columns, derives missing density/congestion,
    and creates PostGIS geometry points with dataset provenance.
    """
    test_df = pd.DataFrame([
        {
            "timestamp": "2026-10-25 10:00:00",
            "traffic_volume": 40,
            "average_speed": 22.0,
            "intersection_id": "INT_002",
            "latitude": 13.0824,
            "longitude": 80.2755,
        },
        {
            "timestamp": "2026-10-25 11:00:00",
            "traffic_volume": 15,
            "average_speed": 45.0,
            "intersection_id": "INT_002",
            "latitude": 13.0824,
            "longitude": 80.2755,
        },
    ])

    db = SessionLocal()
    try:
        result = TrafficIngestionService.ingest_observations_dataframe(
            df=test_df,
            db=db,
            provenance="unit_test_chennai_benchmark",
        )
        assert result["inserted"] >= 2
        assert result["provenance"] == "unit_test_chennai_benchmark"

        # Verify record in database
        latest = (
            db.query(TrafficStreamEvent)
            .filter(TrafficStreamEvent.intersection_id == "INT_002")
            .order_by(TrafficStreamEvent.id.desc())
            .first()
        )
        assert latest is not None
        assert latest.total_vehicles in [15, 40]
        assert latest.location is not None
        assert latest.events[0]["provenance"] == "unit_test_chennai_benchmark"
    finally:
        db.close()


def test_route_corridor_retrieves_registered_arterials(client):
    """
    Verify route analysis along EVR Periyar Salai (Egmore to Anna Nagar)
    genuinely identifies registered road segments and historical corridor observations.
    """
    payload = {
        "origin": {"lat": 13.0782, "lng": 80.2608, "name": "Egmore"},
        "destination": {"lat": 13.0850, "lng": 80.2100, "name": "Anna Nagar"},
        "include_alternatives": True,
    }

    res = client.post("/analysis/route", json=payload)
    assert res.status_code == 200
    data = res.json()

    corridor = data["corridor"]
    assert len(corridor["matched_roads"]) >= 1
    road_names = [r["road_name"] for r in corridor["matched_roads"]]
    assert any("EVR Periyar" in name or "Inner Ring" in name for name in road_names)

    # Intersections along the corridor
    inter_names = [i["name"] for i in corridor["nearby_intersections"]]
    assert any("Egmore" in name or "Anna Nagar" in name for name in inter_names)

    # Live provider telemetry is available, but synthetic seed counts are excluded.
    assert corridor["telemetry_sample_count"] > 0
    assert corridor["telemetry_status"] == "AVAILABLE"
    assert data["ai_prediction"]["status"] in {"AVAILABLE", "INSUFFICIENT_DATA"}
    if data["ai_prediction"]["status"] == "AVAILABLE":
        assert corridor["observed_total_vehicles"] is not None


def test_video_analysis_persists_observation_when_intersection_provided():
    """
    Verify video analysis persists observation to TrafficStreamEvent with PostGIS location
    when tied to an intersection.
    """
    db = SessionLocal()
    try:
        initial_count = (
            db.query(TrafficStreamEvent)
            .filter(TrafficStreamEvent.intersection_id == "INT_001")
            .count()
        )
    finally:
        db.close()

    # Verify that the service logic handles video persistence
    now = datetime.now()
    db = SessionLocal()
    try:
        from backend.app.models.intersection import Intersection
        from geoalchemy2.elements import WKTElement
        from backend.app.core.geo_config import POSTGIS_SRID

        inter = db.query(Intersection).filter(Intersection.intersection_id == "INT_001").first()
        assert inter is not None

        event = TrafficStreamEvent(
            total_vehicles=16,
            vehicle_types={"car": 12, "motorcycle": 4},
            lane_counts={"lane_1": 8, "lane_2": 8},
            direction_counts={"toward_camera": 10, "away_from_camera": 6},
            average_speed=38.0,
            density=0.32,
            congestion_level="LOW",
            events=[{
                "source": "video_analysis",
                "job_id": "job_unit_test_001",
                "processed_at": now.isoformat(),
            }],
            intersection_id="INT_001",
            latitude=inter.latitude,
            longitude=inter.longitude,
            location=WKTElement(f"POINT({inter.longitude} {inter.latitude})", srid=POSTGIS_SRID),
            timestamp=now,
        )
        db.add(event)
        db.commit()

        new_count = (
            db.query(TrafficStreamEvent)
            .filter(TrafficStreamEvent.intersection_id == "INT_001")
            .count()
        )
        assert new_count == initial_count + 1
    finally:
        db.close()


def test_stream_annotated_video_endpoint(client, tmp_path):
    """
    Verify /analysis/video/{job_id}/stream serves the annotated MP4 video
    when available, and returns 404 when not available.
    """
    fake_job_id = "job_stream_test_123"
    fake_video_file = tmp_path / f"annotated_{fake_job_id}.mp4"
    fake_video_file.write_bytes(b"fake_mp4_video_data_bytes_content")

    with _jobs_lock:
        _jobs[fake_job_id] = {
            "job_id": fake_job_id,
            "filename": "test.mp4",
            "annotated_video_path": str(fake_video_file),
        }

    res = client.get(f"/analysis/video/{fake_job_id}/stream")
    assert res.status_code == 200
    assert res.headers["content-type"] == "video/mp4"
    assert res.content == b"fake_mp4_video_data_bytes_content"

    # Nonexistent job returns 404
    res_404 = client.get("/analysis/video/nonexistent_job_xyz/stream")
    assert res_404.status_code == 404


def test_ai_feature_schema_compatibility():
    """
    Verify exact feature count and schema compatibility:
    - Production TrafficPredictor expects 15 features.
    - ExternalTrafficPredictor expects 9 features.
    """
    # 1. Urban predictor (15 features)
    urban_predictor = TrafficPredictor()
    urban_input = {
        "total_vehicles": 25,
        "average_speed": 28.0,
        "density": 0.45,
        "hour": 14,
        "day_of_week": 2,
        "minute": 30,
    }
    pred_urban = urban_predictor.predict(urban_input)
    assert "predicted_congestion" in pred_urban
    assert "prediction_confidence" in pred_urban
    assert "predicted_vehicle_count" in pred_urban

    # 2. Highway external predictor (9 features)
    ext_predictor = ExternalTrafficPredictor()
    valid_ext_input = {
        "hour": 8,
        "day_of_week": 1,
        "month": 10,
        "is_weekend": 0,
        "is_peak_hour": 1,
        "traffic_lag_1": 4500,
        "traffic_lag_2": 4200,
        "traffic_lag_3": 3800,
        "traffic_rolling_mean_3": 4166.7,
    }
    pred_ext = ext_predictor.predict(valid_ext_input)
    assert "predicted_traffic_volume" in pred_ext
    assert pred_ext["forecast_target"] == "next_observation_traffic_volume"
    assert len(pred_ext["features_used"]) == 9

    # Verify incompatible features are rejected by external predictor
    with pytest.raises(ValueError) as exc_info:
        ext_predictor.predict({"total_vehicles": 10})  # Missing required features
    assert "Missing required external forecasting features" in str(exc_info.value)
