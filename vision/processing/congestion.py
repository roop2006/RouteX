def calculate_density(
    vehicle_count: int,
    lane_count: int = 3,
    vehicles_per_lane: int = 10
):

    capacity = lane_count * vehicles_per_lane

    if capacity <= 0:
        return 0.0

    density = vehicle_count / capacity

    return min(density, 1.0)


def classify_congestion(
    density: float,
    average_speed: float
):

    if density >= 0.75 and average_speed <= 15:
        return "HIGH"

    if density >= 0.45 and average_speed <= 30:
        return "MEDIUM"

    return "LOW"