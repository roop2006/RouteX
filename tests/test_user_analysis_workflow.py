import io
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app.core.database import SessionLocal
from backend.app.main import app
from backend.app.services import video_analysis_service as vas


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_location_search_endpoint(client):
    """Verify location autocomplete returns database and preset locations."""
    res = client.get("/analysis/geocoding/search?q=RouteX")
    assert res.status_code == 200
    suggestions = res.json()
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0

    first = suggestions[0]
    assert "name" in first
    assert "lat" in first
    assert "lng" in first
    assert isinstance(first["lat"], (int, float))
    assert isinstance(first["lng"], (int, float))


def test_route_analysis_corridor_with_telemetry(client):
    """
    Test user route calculation near RouteX Test Intersection (INT_001),
    verifying genuine PostGIS corridor correlation and AI model integration.
    """
    payload = {
        "origin": {
            "lat": 13.0827,
            "lng": 80.2707,
            "name": "RouteX Test Intersection (INT_001)"
        },
        "destination": {
            "lat": 13.0824,
            "lng": 80.2755,
            "name": "Chennai Central Junction"
        },
        "include_alternatives": True,
        "mode": "driving"
    }

    res = client.post("/analysis/route", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert "origin" in data
    assert "destination" in data
    assert "selected_route" in data
    assert "corridor" in data
    assert "ai_prediction" in data

    route = data["selected_route"]
    assert route["route_id"]
    assert route["distance_km"] > 0
    assert route["free_flow_duration_minutes"] > 0
    assert route["geometry"]["type"] == "LineString"
    assert len(route["geometry"]["coordinates"]) >= 2

    # Every selectable route carries its own spatial corridor results and AI result.
    with SessionLocal() as db:
        for alternative in data["alternatives"]:
            assert alternative["route_id"]
            assert alternative["corridor"] is not None
            assert alternative["ai_prediction"]["status"] in ("AVAILABLE", "INSUFFICIENT_DATA")
            for road in alternative["corridor"]["matched_roads"]:
                assert road["road_id"] and road["geometry"]
                assert road["match_relation"] in ("INTERSECTS", "NEARBY")
                assert road["distance_to_route_meters"] <= 250
            for intersection in alternative["corridor"]["nearby_intersections"]:
                assert intersection["distance_to_route_meters"] <= 350
            for observation in alternative["corridor"]["traffic_observations"]:
                assert -90 <= observation["latitude"] <= 90
                assert -180 <= observation["longitude"] <= 180
                assert observation["source"]
                is_spatially_matched = db.execute(
                    text("""
                        SELECT ST_DWithin(
                            location::geography,
                            ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)::geography,
                            350
                        )
                        FROM traffic_stream_events
                        WHERE id = :event_id
                    """),
                    {"geom": json.dumps(alternative["geometry"]), "event_id": observation["id"]},
                ).scalar_one()
                assert is_spatially_matched is True

    # Corridor verification
    corridor = data["corridor"]
    assert corridor["traffic_observations"] is not None
    assert corridor["observation_freshness"] in ("FRESH", "RECENT", "HISTORICAL", "UNAVAILABLE")
    assert corridor["telemetry_status"] in ("AVAILABLE", "UNAVAILABLE")
    if corridor["telemetry_status"] == "AVAILABLE":
        assert corridor["observed_average_speed"] is not None
        assert corridor["observed_density"] is not None
        assert data["ai_prediction"]["status"] == "AVAILABLE"
        assert data["ai_prediction"]["predicted_vehicle_count"] is not None
        assert data["ai_prediction"]["prediction_confidence"] is not None


def test_route_analysis_distinguishes_no_telemetry(client):
    """
    Verify that corridors with no telemetry sensors are explicitly marked
    as NO_TELEMETRY rather than falsely claiming low congestion.
    """
    payload = {
        "origin": {
            "lat": 13.0067,
            "lng": 80.2026,
            "name": "Guindy Industrial Node"
        },
        "destination": {
            "lat": 13.0405,
            "lng": 80.2337,
            "name": "T. Nagar"
        },
        "include_alternatives": False
    }

    res = client.post("/analysis/route", json=payload)
    if res.status_code == 503:
        pytest.skip("Routing calculation unavailable: OSRM failed and no connecting PostGIS road matched")
    assert res.status_code == 200
    data = res.json()

    # The corridor far from INT_001 has no stream events in DB
    corridor = data["corridor"]
    if corridor["telemetry_sample_count"] == 0:
        assert corridor["telemetry_status"] == "UNAVAILABLE"
        assert data["selected_route"]["corridor_data_status"] == "NO_TELEMETRY"
        assert data["selected_route"]["congestion_level"] in ("UNAVAILABLE", "NO_TELEMETRY")
        assert data["ai_prediction"]["status"] == "INSUFFICIENT_DATA"


def test_video_upload_validation_rejects_invalid_file(client):
    """Verify server rejects non-video files safely."""
    fake_file = io.BytesIO(b"Not a video file content")
    files = {"file": ("malicious.exe", fake_file, "application/octet-stream")}
    res = client.post("/analysis/video/upload", files=files)
    assert res.status_code == 400
    assert "Unsupported video format" in res.json()["detail"]


def test_video_sample_analysis_lifecycle(client):
    """
    Test launching analysis on existing sample video data/videos/traffic.mp4,
    polling status, and verifying job tracking.
    """
    payload = {
        "video_path": "data/videos/traffic.mp4",
        "intersection_id": "INT_001"
    }

    res = client.post("/analysis/video/sample", json=payload)
    assert res.status_code == 200
    job_info = res.json()
    assert "job_id" in job_info
    job_id = job_info["job_id"]
    assert job_info["status"] in ("PENDING", "PROCESSING")

    # Poll status immediately
    status_res = client.get(f"/analysis/video/{job_id}")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["job_id"] == job_id
    assert status_data["status"] in ("PENDING", "PROCESSING", "COMPLETED")


def test_video_job_cancellation(client):
    """Verify that an ongoing video job can be requested to cancel."""
    payload = {
        "video_path": "data/videos/traffic.mp4",
        "intersection_id": "INT_001"
    }
    launch_res = client.post("/analysis/video/sample", json=payload)
    assert launch_res.status_code == 200
    job_id = launch_res.json()["job_id"]

    cancel_res = client.post(f"/analysis/video/{job_id}/cancel")
    assert cancel_res.status_code in (200, 400)


def test_combined_analysis_rejects_incomplete_video(client):
    """
    Verify combined analysis rejects a job that hasn't finished processing.
    """
    payload = {
        "route_request": {
            "origin": {"lat": 13.0827, "lng": 80.2707},
            "destination": {"lat": 13.0824, "lng": 80.2755}
        },
        "video_job_id": "job_nonexistent_123"
    }
    res = client.post("/analysis/combine", json=payload)
    assert res.status_code == 404


def test_route_analysis_same_origin_and_destination_fails(client):
    """Origin and destination coordinates must be distinct."""
    payload = {
        "origin": {"lat": 13.0827, "lng": 80.2707},
        "destination": {"lat": 13.0827, "lng": 80.2707},
        "include_alternatives": False,
    }
    res = client.post("/analysis/route", json=payload)
    assert res.status_code == 400
    assert "Origin and destination must be different locations" in res.json()["detail"]


def test_location_search_empty_and_fallback(client):
    """Empty query should return default presets rather than failing."""
    res_empty = client.get("/analysis/geocoding/search?q=")
    assert res_empty.status_code == 200
    assert len(res_empty.json()) > 0

    res_unknown = client.get("/analysis/geocoding/search?q=xyz_nonexistent_query_999")
    assert res_unknown.status_code == 200
    assert isinstance(res_unknown.json(), list)


def test_video_upload_empty_file_rejected(client):
    """Empty 0-byte video files must be rejected gracefully."""
    empty_file = io.BytesIO(b"")
    files = {"file": ("empty.mp4", empty_file, "video/mp4")}
    res = client.post("/analysis/video/upload", files=files)
    assert res.status_code == 400
    assert "Uploaded video file is empty" in res.json()["detail"]


def test_video_upload_corrupt_file_rejected(client):
    """Files with valid extension but corrupt media bytes must be rejected."""
    corrupt_file = io.BytesIO(b"FAKE_VIDEO_CONTENT_NOT_DECODABLE")
    files = {"file": ("corrupt.mp4", corrupt_file, "video/mp4")}
    res = client.post("/analysis/video/upload", files=files)
    assert res.status_code == 400
    assert "could not be decoded" in res.json()["detail"]


def test_video_sample_disallows_path_traversal(client):
    """Path traversal outside allowed video directories must be rejected."""
    payload = {
        "video_path": "../../secret.txt",
        "intersection_id": "INT_001",
    }
    res = client.post("/analysis/video/sample", json=payload)
    assert res.status_code == 400
    assert "outside the allowed" in res.json()["detail"]


def test_video_sample_nonexistent_file(client):
    """Missing file within allowed directory returns 404."""
    payload = {
        "video_path": "data/videos/nonexistent_sample.mp4",
        "intersection_id": "INT_001",
    }
    res = client.post("/analysis/video/sample", json=payload)
    assert res.status_code == 404


def test_video_cancel_nonexistent_or_completed_job(client):
    """Canceling a nonexistent or already finished job returns 400."""
    res = client.post("/analysis/video/job_fake_nonexistent_id/cancel")
    assert res.status_code == 400


def test_combined_analysis_associated_corridor_success(client):
    """
    Verify combined analysis successfully correlates a completed video job
    when the video camera is located directly on or within 500m of the route corridor.
    """
    job_id = "job_test_assoc_001"
    now = datetime.now()

    result_data = {
        "job_id": job_id,
        "filename": "traffic.mp4",
        "total_frames": 100,
        "processed_frames": 100,
        "duration_seconds": 4.0,
        "fps": 25.0,
        "total_vehicles_detected": 14,
        "vehicle_types": {"car": 10, "truck": 2, "motorcycle": 2},
        "lane_counts": {"lane_1": 7, "lane_2": 7},
        "direction_counts": {"toward_camera": 8, "away_from_camera": 6, "unknown": 0},
        "line_crossing_counts": {"car": 5},
        "line_crossing_total": 5,
        "average_speed": 42.0,
        "density": 0.28,
        "congestion_level": "LOW",
        "anomaly_events": [],
        "frame_samples": [],
        "preview_image_base64": None,
        "intersection_id": "INT_001",
        "ai_prediction": {
            "model_name": "routex_production_predictor",
            "predicted_congestion": "LOW",
            "prediction_confidence": 0.92,
            "predicted_vehicle_count": 15.0,
        },
        "processed_at": now.isoformat(),
    }

    with vas._jobs_lock:
        vas._jobs[job_id] = {
            "job_id": job_id,
            "filename": "traffic.mp4",
            "file_path": "data/videos/traffic.mp4",
            "intersection_id": "INT_001",
            "status": "COMPLETED",
            "progress_percent": 100.0,
            "current_fps": 25.0,
            "frames_processed": 100,
            "total_frames": 100,
            "error": None,
            "cancel_requested": False,
            "result": result_data,
            "created_at": now,
        }

    payload = {
        "route_request": {
            "origin": {"lat": 13.0827, "lng": 80.2707, "name": "RouteX Test Intersection (INT_001)"},
            "destination": {"lat": 13.0824, "lng": 80.2755, "name": "Chennai Central Junction"},
            "include_alternatives": False,
        },
        "video_job_id": job_id,
    }

    res = client.post("/analysis/combine", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_associated"] is True
    assert "INT_001" in data["association_reason"]
    assert data["integrated_traffic_summary"]["corridor_status"] == "INTEGRATED_VISION_TELEMETRY"
    assert data["integrated_traffic_summary"]["video_vehicles_observed"] == 14
    assert data["route_analysis"] is not None
    assert data["video_analysis"] is not None


def test_combined_analysis_standalone_camera_no_location(client):
    """
    Verify that videos with no location metadata (e.g. STANDALONE_CAMERA)
    are explicitly marked as unassociated without failing or inventing an association.
    """
    job_id = "job_test_standalone_002"
    now = datetime.now()

    result_data = {
        "job_id": job_id,
        "filename": "standalone.mp4",
        "total_frames": 60,
        "processed_frames": 60,
        "duration_seconds": 2.5,
        "fps": 24.0,
        "total_vehicles_detected": 8,
        "vehicle_types": {"car": 8},
        "lane_counts": {},
        "direction_counts": {},
        "line_crossing_counts": {},
        "line_crossing_total": 0,
        "average_speed": 35.0,
        "density": 0.2,
        "congestion_level": "LOW",
        "anomaly_events": [],
        "frame_samples": [],
        "preview_image_base64": None,
        "intersection_id": "STANDALONE_CAMERA",
        "ai_prediction": None,
        "processed_at": now.isoformat(),
    }

    with vas._jobs_lock:
        vas._jobs[job_id] = {
            "job_id": job_id,
            "filename": "standalone.mp4",
            "file_path": "data/uploads/standalone.mp4",
            "intersection_id": "STANDALONE_CAMERA",
            "status": "COMPLETED",
            "progress_percent": 100.0,
            "current_fps": 24.0,
            "frames_processed": 60,
            "total_frames": 60,
            "error": None,
            "cancel_requested": False,
            "result": result_data,
            "created_at": now,
        }

    payload = {
        "route_request": {
            "origin": {"lat": 13.0827, "lng": 80.2707},
            "destination": {"lat": 13.0824, "lng": 80.2755},
        },
        "video_job_id": job_id,
    }

    res = client.post("/analysis/combine", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_associated"] is False
    assert "no camera coordinates" in data["association_reason"].lower()
    assert data["integrated_traffic_summary"]["corridor_status"] == "DISCONNECTED"
    # Both independent results must still be provided
    assert data["route_analysis"] is not None
    assert data["video_analysis"] is not None


def test_route_analysis_recommendation_and_ranking(client):
    """
    Verify route analysis calculates road-following geometry, ranks routes,
    flags the recommended alternative with rank 1, and provides explainable recommendation text.
    """
    payload = {
        "origin": {"lat": 13.0827, "lng": 80.2707, "name": "INT_001"},
        "destination": {"lat": 13.0824, "lng": 80.2755, "name": "Chennai Central"},
        "include_alternatives": True,
    }

    res = client.post("/analysis/route", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert "selected_route" in data
    assert "alternatives" in data
    assert len(data["alternatives"]) >= 1

    selected = data["selected_route"]
    assert selected["rank"] == 1
    assert selected["is_recommended"] is True
    assert selected["recommendation_reason"] is not None
    assert selected["geometry"]["type"] == "LineString"
    assert len(selected["geometry"]["coordinates"]) >= 2

    # Verify recommendation fields on top-level response
    assert data["recommended_route_summary"] is not None
    assert data["recommendation_explanation"] is not None
    assert data["recommendation_basis"] is not None

    # Verify all alternatives have ranking and road-following geometry
    for idx, alt in enumerate(data["alternatives"]):
        assert alt["rank"] == idx + 1
        assert alt["geometry"]["type"] == "LineString"
        assert len(alt["geometry"]["coordinates"]) >= 2
        assert alt["distance_meters"] > 0
        assert alt["free_flow_duration_seconds"] > 0


def test_video_density_and_congestion_metric_accuracy():
    """
    Verify density and congestion classification accuracy.
    Instantaneous density must reflect current occupancy (vehicles / capacity)
    and not saturate artificially from cumulative counts.
    """
    from vision.processing.congestion import calculate_density, classify_congestion

    # Test density with 6 vehicles on a 3-lane road (capacity = 30)
    density_low = calculate_density(vehicle_count=6, lane_count=3, vehicles_per_lane=10)
    assert round(density_low, 2) == 0.20
    congestion_low = classify_congestion(density=density_low, average_speed=40.0)
    assert congestion_low == "LOW"

    # Test density with 25 vehicles (near capacity) at low speed (10 km/h) -> HIGH congestion
    density_high = calculate_density(vehicle_count=25, lane_count=3, vehicles_per_lane=10)
    assert round(density_high, 2) == 0.83
    congestion_high = classify_congestion(density=density_high, average_speed=10.0)
    assert congestion_high == "HIGH"


