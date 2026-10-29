from vision.processing.congestion import (
    calculate_density,
    classify_congestion
)


class TrafficIntelligence:

    def __init__(self):

        self.lane_count = 3
        self.vehicles_per_lane = 10

    def analyze(
        self,
        traffic_data,
        average_speed=0.0,
        anomaly_events=None
    ):

        total_vehicles = (
            traffic_data["total_vehicles"]
        )

        density = calculate_density(
            total_vehicles,
            self.lane_count,
            self.vehicles_per_lane
        )

        congestion = classify_congestion(
            density,
            average_speed
        )

        tracks = traffic_data["tracks"]

        direction_counts = {
            "toward_camera": 0,
            "away_from_camera": 0,
            "unknown": 0
        }

        for track in tracks:

            direction = track.get(
                "direction",
                "unknown"
            )

            if direction in direction_counts:
                direction_counts[direction] += 1
            else:
                direction_counts["unknown"] += 1

        return {
            "total_vehicles": total_vehicles,

            "vehicle_types":
                traffic_data["vehicle_types"],

            "lane_counts":
                traffic_data.get(
                    "lane_counts",
                    {}
                ),

            "direction_counts":
                direction_counts,

            "average_speed":
                round(average_speed, 2),

            "density":
                round(density, 2),

            "congestion_level":
                congestion,

            "events":
                anomaly_events or []
        }