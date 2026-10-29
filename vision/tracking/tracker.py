from ultralytics import YOLO


class VehicleTracker:

    def __init__(
        self,
        model_path="yolo11n.pt",
        confidence=0.40
    ):
        self.model = YOLO(model_path)
        self.confidence = confidence

    def track(self, frame):

        results = self.model.track(
            frame,
            persist=True,
            conf=self.confidence,
            tracker="botsort.yaml",
            verbose=False
        )

        return results[0]