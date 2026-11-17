from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TrafficEventCreate(BaseModel):
    total_vehicles: int = Field(ge=0)

    vehicle_types: dict[str, float]

    lane_counts: dict[str, float]

    direction_counts: dict[str, float]

    average_speed: float = Field(ge=0)

    density: float = Field(ge=0)

    congestion_level: str = Field(
        min_length=1,
        max_length=20
    )

    events: list[dict[str, Any]] = []


class TrafficEventResponse(BaseModel):
    id: int

    total_vehicles: int | None

    vehicle_types: dict[str, float]

    lane_counts: dict[str, float]

    direction_counts: dict[str, float]

    average_speed: float | None

    density: float | None

    congestion_level: str

    events: list[dict[str, Any]]

    timestamp: datetime

    model_config = {"from_attributes": True}
