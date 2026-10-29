import time
import math


class SpeedEstimator:

    def __init__(self, pixels_per_meter=8.0):

        self.pixels_per_meter = pixels_per_meter

        self.previous_positions = {}
        self.previous_times = {}

        self.speeds = {}

    def update(self, tracks, current_time=None):

        if current_time is None:
            current_time = time.time()

        for track in tracks:

            track_id = track["track_id"]

            x, y = track["center"]

            previous_position = self.previous_positions.get(
                track_id
            )

            previous_time = self.previous_times.get(
                track_id
            )

            if (
                previous_position is not None
                and previous_time is not None
            ):

                previous_x, previous_y = previous_position

                pixel_distance = math.sqrt(
                    (x - previous_x) ** 2
                    + (y - previous_y) ** 2
                )

                time_difference = (
                    current_time - previous_time
                )

                if time_difference > 0:

                    distance_meters = (
                        pixel_distance
                        / self.pixels_per_meter
                    )

                    speed_mps = (
                        distance_meters
                        / time_difference
                    )

                    speed_kmh = speed_mps * 3.6

                    self.speeds[track_id] = speed_kmh

            self.previous_positions[track_id] = (x, y)
            self.previous_times[track_id] = current_time

        return self.speeds

    def get_average_speed(self):

        if not self.speeds:
            return 0.0

        return sum(
            self.speeds.values()
        ) / len(self.speeds)