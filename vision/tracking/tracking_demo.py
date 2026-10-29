import cv2

from vision.tracking.tracker import VehicleTracker


VIDEO_PATH = "data/videos/traffic.mp4"


def main():

    tracker = VehicleTracker()

    cap = cv2.VideoCapture(VIDEO_PATH)

    if not cap.isOpened():
        raise RuntimeError(
            f"Unable to open video: {VIDEO_PATH}"
        )

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        result = tracker.track(frame)

        annotated_frame = result.plot()

        cv2.imshow(
            "RouteX - Vehicle Tracking",
            annotated_frame
        )

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()