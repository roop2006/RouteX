def calculate_density(
    vehicle_count: int,
    capacity: int
) -> float:

    if capacity <= 0:
        return 0.0

    density = vehicle_count / capacity

    return min(density, 1.0)