
import cv2

from vision.tracking.tracker import VehicleTracker
from vision.processing.traffic_processor import TrafficProcessor
from vision.processing.line_counter import LineCounter
from vision.processing.anomaly_detector import AnomalyDetector
from vision.processing.traffic_intelligence import TrafficIntelligence
from vision.processing.speed_estimator import SpeedEstimator
from vision.processing.lane_detector import LaneDetector
from vision.processing.direction_detector import DirectionDetector
from vision.processing.event_builder import build_events
from vision.streaming.kafka_producer import TrafficKafkaProducer
from vision.config import CAMERA_CONFIG


VIDEO_PATH = "data/videos/traffic.mp4"

# Virtual counting line position
LINE_Y = 300


def main():

    # --------------------------------
    # 1. Initialize RouteX components
    # --------------------------------
    tracker = VehicleTracker()
    processor = TrafficProcessor()
    line_counter = LineCounter(line_y=LINE_Y)
    anomaly_detector = AnomalyDetector()
    traffic_intelligence = TrafficIntelligence()
    kafka_producer = TrafficKafkaProducer()

    # Speed estimator
    speed_estimator = SpeedEstimator(
        pixels_per_meter=8.0
    )

    # Lane detector
    lane_detector = LaneDetector(
        lane_boundaries=[
            (0, 250),
            (250, 500),
            (500, 800)
        ]
    )

    # Direction detector
    direction_detector = DirectionDetector()

    # --------------------------------
    # 2. Open traffic video
    # --------------------------------
    cap = cv2.VideoCapture(VIDEO_PATH)

    if not cap.isOpened():
        raise RuntimeError(
            f"Unable to open video: {VIDEO_PATH}"
        )

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        # --------------------------------
        # 3. Track vehicles
        # --------------------------------
        result = tracker.track(frame)

        # --------------------------------
        # 4. Process traffic information
        # --------------------------------
        traffic_data = processor.process(result)

        # --------------------------------
        # 4.1 Assign vehicles to lanes
        # --------------------------------
        tracks, lane_counts = lane_detector.assign_lanes(
            traffic_data["tracks"]
        )

        traffic_data["tracks"] = tracks
        traffic_data["lane_counts"] = lane_counts

        # --------------------------------
        # 4.2 Detect vehicle direction
        # --------------------------------
        tracks, directions = direction_detector.update(
            traffic_data["tracks"]
        )

        traffic_data["tracks"] = tracks
        traffic_data["directions"] = directions

        # --------------------------------
        # 5. Estimate vehicle speeds
        # --------------------------------
        speeds = speed_estimator.update(
            traffic_data["tracks"]
        )

        average_speed = speed_estimator.get_average_speed()

        # --------------------------------
        # 6. Detect anomalies
        # --------------------------------
        anomaly_events = anomaly_detector.detect(
            traffic_data["tracks"]
        )
        events = build_events(
            anomaly_events
        )

        # --------------------------------
        # 7. Analyze traffic intelligence
        # --------------------------------
        intelligence = traffic_intelligence.analyze(
            traffic_data,
            average_speed=average_speed,
            anomaly_events=events
        )

        # --------------------------------
        # 7.1 Send traffic event to Kafka
        # --------------------------------
        payload = {
            **intelligence,
            **CAMERA_CONFIG
        }
        kafka_producer.send_event(payload)

        # --------------------------------
        # 8. Count vehicle types crossing line
        # --------------------------------
        crossed_types = line_counter.update(
            traffic_data["tracks"]
        )

        # --------------------------------
        # 9. Draw YOLO tracking results
        # --------------------------------
        annotated_frame = result.plot()

        # --------------------------------
        # 10. Display total unique vehicles
        # --------------------------------
        total = traffic_data["total_vehicles"]

        cv2.putText(
            annotated_frame,
            f"Total vehicles: {total}",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        # --------------------------------
        # 11. Display vehicle type counts
        # --------------------------------
        vehicle_types = traffic_data["vehicle_types"]

        y = 70

        for vehicle_type, count in vehicle_types.items():

            cv2.putText(
                annotated_frame,
                f"{vehicle_type}: {count}",
                (20, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )

            y += 30

        # --------------------------------
        # 12. Display vehicle types crossed
        # --------------------------------
        cv2.putText(
            annotated_frame,
            "Vehicle types crossed:",
            (20, y + 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        y += 40

        for vehicle_type, count in crossed_types.items():

            cv2.putText(
                annotated_frame,
                f"{vehicle_type}: {count}",
                (20, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )

            y += 30

        # --------------------------------
        # 13. Display traffic density
        # --------------------------------
        cv2.putText(
            annotated_frame,
            f"Density: {intelligence['density']:.2f}",
            (20, y + 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        y += 40

        # --------------------------------
        # 14. Display average speed
        # --------------------------------
        cv2.putText(
            annotated_frame,
            f"Average speed: {average_speed:.1f} km/h",
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2
        )

        y += 30

        # --------------------------------
        # 15. Display congestion level
        # --------------------------------
        cv2.putText(
            annotated_frame,
            f"Congestion: {intelligence['congestion_level']}",
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        y += 30

        # --------------------------------
        # 16. Display lane vehicle counts
        # --------------------------------
        cv2.putText(
            annotated_frame,
            "Lane vehicles:",
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2
        )

        y += 30

        for lane, count in lane_counts.items():

            cv2.putText(
                annotated_frame,
                f"{lane}: {count}",
                (20, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )

            y += 28

        y += 10

        # --------------------------------
        # 17. Display vehicle direction
        # --------------------------------
        cv2.putText(
            annotated_frame,
            "Vehicle direction:",
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2
        )

        y += 30

        toward_count = sum(
            1
            for direction in directions.values()
            if direction == "toward_camera"
        )

        away_count = sum(
            1
            for direction in directions.values()
            if direction == "away_from_camera"
        )

        cv2.putText(
            annotated_frame,
            f"Toward camera: {toward_count}",
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2
        )

        y += 28

        cv2.putText(
            annotated_frame,
            f"Away from camera: {away_count}",
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2
        )

        y += 30

        # --------------------------------
        # 18. Display anomaly count
        # --------------------------------
        cv2.putText(
            annotated_frame,
            f"Anomalies: {len(anomaly_events)}",
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        # --------------------------------
        # 19. Show RouteX output
        # --------------------------------
        cv2.imshow(
            "RouteX - Traffic Intelligence",
            annotated_frame
        )

        # Press Q to exit
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    # --------------------------------
    # 20. Release resources
    # --------------------------------
    cap.release()
    cv2.destroyAllWindows()
    kafka_producer.close()


if __name__ == "__main__":
    main()
