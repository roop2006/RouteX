from ultralytics import YOLO

from .classes import VEHICLE_CLASSES


class YOLODetector:

    def __init__(
        self,
        model_path="yolo11n.pt",
        confidence=0.40
    ):
        self.model = YOLO(model_path)
        self.confidence = confidence

    def detect(self, frame):

        results = self.model(
            frame,
            conf=self.confidence,
            verbose=False
        )

        detections = []

        result = results[0]

        if result.boxes is None:
            return detections

        for box in result.boxes:

            class_id = int(
                box.cls[0].item()
            )

            confidence = float(
                box.conf[0].item()
            )

            if class_id not in VEHICLE_CLASSES:
                continue

            x1, y1, x2, y2 = map(
                int,
                box.xyxy[0].tolist()
            )

            detections.append({
                "class_id": class_id,
                "vehicle_type": VEHICLE_CLASSES[class_id],
                "confidence": confidence,
                "bbox": [x1, y1, x2, y2]
            })

        return detections