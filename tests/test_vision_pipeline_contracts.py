import json
import pytest
from geoalchemy2.elements import WKTElement

from vision.processing.vehicle_counter import count_vehicles, VehicleCounter
from vision.processing.traffic_intelligence import TrafficIntelligence
from vision.config import CAMERA_CONFIG
from vision.streaming.kafka_config import TRAFFIC_TOPIC, KAFKA_BOOTSTRAP_SERVERS, KAFKA_GROUP_ID


def test_count_vehicles():
    detections = [
        {"bbox": (10, 10, 50, 50), "vehicle_type": "car", "confidence": 0.95},
        {"bbox": (60, 60, 100, 100), "vehicle_type": "car", "confidence": 0.91},
        {"bbox": (120, 120, 200, 200), "vehicle_type": "truck", "confidence": 0.88},
    ]
    counts = count_vehicles(detections)
    assert counts == {"car": 2, "truck": 1}


def test_vehicle_counter_class():
    counter = VehicleCounter()
    tracks = [
        {"track_id": 1, "vehicle_type": "car"},
        {"track_id": 2, "vehicle_type": "bus"},
        {"track_id": 1, "vehicle_type": "car"},  # Duplicate track_id
    ]
    counter.update(tracks)
    assert counter.get_total() == 2
    assert counter.get_type_counts() == {"car": 1, "bus": 1}


def test_traffic_intelligence_analyze_schema():
    ti = TrafficIntelligence()
    mock_traffic_data = {
        "total_vehicles": 15,
        "vehicle_types": {"car": 10, "truck": 5},
        "lane_counts": {"lane_1": 8, "lane_2": 7},
        "tracks": [
            {"track_id": 1, "vehicle_type": "car", "direction": "toward_camera"},
            {"track_id": 2, "vehicle_type": "truck", "direction": "away_from_camera"},
        ],
    }
    result = ti.analyze(mock_traffic_data, average_speed=40.0)

    assert result["total_vehicles"] == 15
    assert result["average_speed"] == 40.0
    assert result["density"] >= 0.0
    assert result["congestion_level"] in ["LOW", "MEDIUM", "HIGH"]
    assert "vehicle_types" in result
    assert "lane_counts" in result
    assert "direction_counts" in result
    assert result["direction_counts"]["toward_camera"] == 1
    assert result["direction_counts"]["away_from_camera"] == 1


def test_kafka_payload_compatibility():
    ti = TrafficIntelligence()
    mock_traffic_data = {
        "total_vehicles": 8,
        "vehicle_types": {"car": 8},
        "tracks": [],
    }
    intelligence = ti.analyze(mock_traffic_data, average_speed=50.0)
    payload = {**intelligence, **CAMERA_CONFIG}

    # Verify JSON serializability
    serialized = json.dumps(payload)
    deserialized = json.loads(serialized)

    assert deserialized["total_vehicles"] == 8
    assert deserialized["camera_id"] == "CAM_001"
    assert deserialized["intersection_id"] == "INT_001"
    assert "latitude" in deserialized
    assert "longitude" in deserialized
    assert TRAFFIC_TOPIC == "routex-traffic-events"
    assert KAFKA_BOOTSTRAP_SERVERS == "localhost:9092"
    assert KAFKA_GROUP_ID == "routex-postgres-consumer"
