from collections import Counter


class LineCounter:

    def __init__(self, line_y: int):

        self.line_y = line_y

        self.previous_positions = {}

        self.counted_ids = set()

        self.vehicle_types = {}

    def update(self, tracks):

        for track in tracks:

            track_id = track["track_id"]
            center_y = track["center"][1]
            vehicle_type = track["vehicle_type"]

            previous_y = self.previous_positions.get(track_id)

            if previous_y is not None:

                crossed = (
                    previous_y < self.line_y
                    and center_y >= self.line_y
                )

                if crossed and track_id not in self.counted_ids:

                    self.counted_ids.add(track_id)

                    self.vehicle_types[track_id] = vehicle_type

            self.previous_positions[track_id] = center_y

        return self.get_type_counts()

    def get_type_counts(self):

        return dict(
            Counter(self.vehicle_types.values())
        )