import cv2

from vision.detection.yolo_detector import YOLODetector
from vision.processing.vehicle_counter import count_vehicles


VIDEO_PATH = "data/videos/traffic.mp4"


def main():

    detector = YOLODetector()

    cap = cv2.VideoCapture(VIDEO_PATH)

    if not cap.isOpened():
        raise RuntimeError(
            f"Unable to open video: {VIDEO_PATH}"
        )

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        detections = detector.detect(frame)

        counts = count_vehicles(detections)

        annotated_frame = frame.copy()

        for detection in detections:

            x1, y1, x2, y2 = detection["bbox"]

            vehicle_type = detection["vehicle_type"]
            confidence = detection["confidence"]

            cv2.rectangle(
                annotated_frame,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                2
            )

            label = (
                f"{vehicle_type} "
                f"{confidence:.2f}"
            )

            cv2.putText(
                annotated_frame,
                label,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2
            )

        y = 30

        for vehicle_type, count in counts.items():

            text = f"{vehicle_type}: {count}"

            cv2.putText(
                annotated_frame,
                text,
                (20, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )

            y += 30

        cv2.imshow(
            "RouteX - Traffic Intelligence",
            annotated_frame
        )

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()