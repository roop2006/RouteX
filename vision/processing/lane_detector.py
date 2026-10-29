class LaneDetector:

    def __init__(self, lane_boundaries):
        """
        lane_boundaries:
        List of x-coordinate ranges for each lane.

        Example:
        [
            (0, 250),
            (250, 500),
            (500, 800)
        ]
        """

        self.lane_boundaries = lane_boundaries

    def get_lane(self, center):

        x, y = center

        for index, (x_min, x_max) in enumerate(
            self.lane_boundaries,
            start=1
        ):

            if x_min <= x < x_max:
                return f"lane_{index}"

        return "unknown"

    def assign_lanes(self, tracks):

        lane_counts = {}

        for track in tracks:

            lane = self.get_lane(
                track["center"]
            )

            track["lane"] = lane

            if lane != "unknown":

                lane_counts[lane] = (
                    lane_counts.get(lane, 0) + 1
                )

        return tracks, lane_counts