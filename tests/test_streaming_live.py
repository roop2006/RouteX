"""Opt-in real sample-video -> Kafka -> PostgreSQL/Redis -> FastAPI check.

Uses a temporary Kafka topic, prefixed Redis keys and a rolled-back database
transaction. It never publishes sample detections as operational live traffic.
"""
import json
import os
from uuid import uuid4

import pytest


@pytest.mark.skipif(os.getenv("ROUTEX_RUN_STREAMING_SMOKE") != "1", reason="Requires local Kafka, Redis, PostGIS and YOLO artifact")
def test_real_sample_video_to_live_api(monkeypatch):
    import cv2
    from fastapi.testclient import TestClient
    from kafka import KafkaConsumer
    from kafka.admin import KafkaAdminClient, NewTopic
    from sqlalchemy.orm import Session
    from backend.app.core.database import engine, get_db
    from backend.app.main import app
    from backend.app.models.traffic_stream_event import TrafficStreamEvent
    from backend.app.services.live_traffic_service import live_traffic_service
    from vision.config import CAMERA_CONFIG
    from vision.tracking.tracker import VehicleTracker
    from vision.processing.traffic_processor import TrafficProcessor
    from vision.processing.traffic_intelligence import TrafficIntelligence
    from vision.processing.speed_estimator import SpeedEstimator
    from vision.processing.lane_detector import LaneDetector
    from vision.processing.direction_detector import DirectionDetector
    from vision.streaming import event_storage, kafka_producer
    from vision.streaming.kafka_config import KAFKA_BOOTSTRAP_SERVERS
    from vision.streaming.kafka_consumer import process_kafka_payload, kafka_message_id
    from vision.streaming.redis_client import TrafficRedis

    topic = f"routex-verification-{uuid4().hex}"
    admin = KafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    producer = consumer = connection = transaction = session = None
    cache = TrafficRedis()
    original_call = TrafficRedis._call
    keys = set()

    def isolated_cache(self, operation, key, *args, **kwargs):
        isolated_key = f"{topic}:{key}"
        keys.add(isolated_key)
        return original_call(self, operation, isolated_key, *args, **kwargs)

    cap = cv2.VideoCapture("data/videos/traffic.mp4")
    try:
        admin.create_topics([NewTopic(topic, 1, 1)])
        monkeypatch.setattr(kafka_producer, "TRAFFIC_TOPIC", topic)
        monkeypatch.setattr(TrafficRedis, "_call", isolated_cache)
        monkeypatch.setattr(TrafficRedis, "_unavailable_until", 0)
        monkeypatch.setattr(live_traffic_service, "redis_client", cache)
        connection = engine.connect()
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        monkeypatch.setattr(event_storage, "SessionLocal", lambda: Session(bind=connection, join_transaction_mode="create_savepoint"))
        app.dependency_overrides[get_db] = lambda: session

        tracker, processor = VehicleTracker(), TrafficProcessor()
        intelligence, speed = TrafficIntelligence(), SpeedEstimator(pixels_per_meter=8.0)
        lanes, direction = LaneDetector(lane_boundaries=[(0, 250), (250, 500), (500, 800)]), DirectionDetector()
        fps = cap.get(cv2.CAP_PROP_FPS)
        assert cap.isOpened() and fps > 0
        for index in range(12):
            ok, frame = cap.read()
            assert ok
            data = processor.process(tracker.track(frame))
            data["tracks"], data["lane_counts"] = lanes.assign_lanes(data["tracks"])
            data["tracks"], _ = direction.update(data["tracks"])
            speed.update(data["tracks"], current_time=index / fps)
        payload = {**intelligence.analyze(data, average_speed=speed.get_average_speed()),
                   **CAMERA_CONFIG, "source": "verification_sample_video"}
        assert payload["total_vehicles"] > 0
        producer = kafka_producer.TrafficKafkaProducer()
        producer.send_event(payload)
        consumer = KafkaConsumer(topic, bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                                 auto_offset_reset="earliest", enable_auto_commit=False,
                                 group_id=topic, consumer_timeout_ms=15000)
        message = next(iter(consumer))
        message_id = kafka_message_id(message.topic, message.partition, message.offset)
        stored = process_kafka_payload(json.loads(message.value), message_id, redis_client=cache)
        assert stored.total_vehicles == payload["total_vehicles"]
        assert stored.intersection_id == CAMERA_CONFIG["intersection_id"]
        assert session.query(TrafficStreamEvent).filter_by(source_event_id=message_id).count() == 1
        assert cache.get_latest()["total_vehicles"] == stored.total_vehicles
        assert process_kafka_payload(json.loads(message.value), message_id, redis_client=cache) is None
        # No lifespan run: the app is already initialized; avoid committing seed work.
        client = TestClient(app)
        try:
            response = client.get("/live-traffic/")
        finally:
            client.close()
        assert response.status_code == 200
        assert response.json()["source"] == "verification_sample_video"
        assert response.json()["total_vehicles"] == payload["total_vehicles"]
        assert response.json()["intersection_id"] == CAMERA_CONFIG["intersection_id"]
    finally:
        cap.release()
        app.dependency_overrides.pop(get_db, None)
        if session is not None:
            session.close()
        if transaction is not None:
            transaction.rollback()
        if connection is not None:
            connection.close()
        if consumer is not None:
            consumer.close()
        if producer is not None:
            producer.close()
        if keys:
            cache.client.delete(*keys)
        cache.client.close()
        admin.delete_topics([topic])
        admin.close()
