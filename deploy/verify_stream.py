"""Real video -> existing Kafka daemon -> DB/cache/API. Use a disposable stack.

Writes clearly labelled sample-video verification observations; no traffic is invented.
"""
import argparse
import time
from uuid import uuid4
import cv2
import httpx
from sqlalchemy import text
from backend.app.core.database import SessionLocal
from vision.tracking.tracker import VehicleTracker
from vision.processing.traffic_processor import TrafficProcessor
from vision.processing.traffic_intelligence import TrafficIntelligence
from vision.processing.speed_estimator import SpeedEstimator
from vision.streaming.kafka_producer import TrafficKafkaProducer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('video')
    parser.add_argument('--disposable-stack', action='store_true', required=True)
    args = parser.parse_args()
    cap = cv2.VideoCapture(args.video)
    producer = None
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        assert cap.isOpened() and fps > 0
        tracker, processor, speed = VehicleTracker(), TrafficProcessor(), SpeedEstimator()
        for frame_index in range(12):
            ok, frame = cap.read()
            assert ok
            data = processor.process(tracker.track(frame))
            speed.update(data['tracks'], current_time=frame_index / fps)
        payload = TrafficIntelligence().analyze(data, average_speed=speed.get_average_speed())
        payload.update(source='validation_sample_video', verification_run_id=str(uuid4()),
                       events=[{'source': 'validation_sample_video', 'description': 'Disposable-stack acceptance test'}])
        producer = TrafficKafkaProducer()
        record = producer.send_event(payload)
        identity = f'{record.topic}:{record.partition}:{record.offset}'
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            with SessionLocal() as db:
                count = db.execute(text('SELECT count(*) FROM traffic_stream_events WHERE source_event_id=:id'), {'id': identity}).scalar_one()
            if count == 1:
                break
            time.sleep(1)
        assert count == 1, 'Consumer did not persist the real broker message'
        latest = httpx.get('http://backend:8001/live-traffic/', timeout=10).json()
        assert latest.get('verification_run_id') == payload['verification_run_id']
        assert latest['total_vehicles'] == payload['total_vehicles']
        print(f"PASS: real sample video -> running Kafka consumer -> PostgreSQL -> Redis -> API ({payload['total_vehicles']} measured vehicles)")
    finally:
        cap.release()
        if producer:
            producer.close()


if __name__ == '__main__':
    main()
