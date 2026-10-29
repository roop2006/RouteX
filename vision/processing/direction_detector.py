class DirectionDetector:

    def __init__(self, threshold=2):

        self.previous_positions = {}
        self.threshold = threshold

    def update(self, tracks):

        directions = {}

        for track in tracks:

            track_id = track["track_id"]
            x, y = track["center"]

            previous = self.previous_positions.get(track_id)

            direction = "unknown"

            if previous is not None:

                previous_x, previous_y = previous

                delta_y = y - previous_y

                if delta_y > self.threshold:
                    direction = "toward_camera"

                elif delta_y < -self.threshold:
                    direction = "away_from_camera"

            self.previous_positions[track_id] = (x, y)

            directions[track_id] = direction

            track["direction"] = direction

        return tracks, directions