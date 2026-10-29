from vision.detection.classes import VEHICLE_CLASSES


def extract_tracks(result):

    tracks = []

    if result.boxes is None:
        return tracks

    if result.boxes.id is None:
        return tracks

    boxes = result.boxes

    for i in range(len(boxes)):

        class_id = int(
            boxes.cls[i].item()
        )

        if class_id not in VEHICLE_CLASSES:
            continue

        track_id = int(
            boxes.id[i].item()
        )

        confidence = float(
            boxes.conf[i].item()
        )

        x1, y1, x2, y2 = map(
            int,
            boxes.xyxy[i].tolist()
        )

        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2

        tracks.append({
            "track_id": track_id,
            "vehicle_type": VEHICLE_CLASSES[class_id],
            "confidence": confidence,
            "bbox": [x1, y1, x2, y2],
            "center": [center_x, center_y]
        })

    return tracks