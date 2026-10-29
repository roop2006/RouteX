from collections import Counter


def count_vehicles(detections):
    return dict(Counter(d.get("vehicle_type", "unknown") for d in detections))


class VehicleCounter:

    def __init__(self):
        self.seen_ids = set()
        self.vehicle_types = {}

    def update(self, tracks):

        for track in tracks:

            track_id = track["track_id"]
            vehicle_type = track["vehicle_type"]

            self.seen_ids.add(track_id)

            self.vehicle_types[track_id] = vehicle_type

    def get_total(self):

        return len(self.seen_ids)

    def get_type_counts(self):

        return dict(
            Counter(self.vehicle_types.values())
        )