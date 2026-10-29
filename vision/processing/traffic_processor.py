from vision.tracking.tracking_data import extract_tracks
from vision.processing.vehicle_counter import VehicleCounter


class TrafficProcessor:

    def __init__(self):

        self.counter = VehicleCounter()

    def process(self, result):

        tracks = extract_tracks(result)

        self.counter.update(tracks)

        return {
            "tracks": tracks,
            "total_vehicles": self.counter.get_total(),
            "vehicle_types": self.counter.get_type_counts()
        }