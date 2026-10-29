import math


class AnomalyDetector:

    def __init__(
        self,
        stop_threshold=2,
        sudden_movement_threshold=80
    ):

        self.previous_positions = {}
        self.stop_threshold = stop_threshold
        self.sudden_movement_threshold = (
            sudden_movement_threshold
        )

    def detect(self, tracks):

        events = []

        for track in tracks:

            track_id = track["track_id"]

            x, y = track["center"]

            previous = self.previous_positions.get(
                track_id
            )

            if previous is not None:

                previous_x, previous_y = previous

                movement = math.sqrt(
                    (x - previous_x) ** 2
                    + (y - previous_y) ** 2
                )

                if movement < self.stop_threshold:

                    events.append({
                        "event_type":
                            "possible_stopped_vehicle",

                        "severity": "LOW",

                        "vehicle_id": track_id,

                        "vehicle_type":
                            track["vehicle_type"]
                    })

                elif movement > self.sudden_movement_threshold:

                    events.append({
                        "event_type":
                            "abnormal_vehicle_movement",

                        "severity": "MEDIUM",

                        "vehicle_id": track_id,

                        "vehicle_type":
                            track["vehicle_type"]
                    })

            self.previous_positions[
                track_id
            ] = (x, y)

        return events