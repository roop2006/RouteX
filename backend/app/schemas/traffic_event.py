from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TrafficEventCreate(BaseModel):
    total_vehicles: int = Field(ge=0)

    vehicle_types: dict[str, int]

    lane_counts: dict[str, int]

    direction_counts: dict[str, int]

    average_speed: float = Field(ge=0)

    density: float = Field(ge=0)

    congestion_level: str = Field(
        min_length=1,
        max_length=20
    )

    events: list[dict[str, Any]] = []


class TrafficEventResponse(BaseModel):
    id: int

    total_vehicles: int

    vehicle_types: dict[str, int]

    lane_counts: dict[str, int]

    direction_counts: dict[str, int]

    average_speed: float

    density: float

    congestion_level: str

    events: list[dict[str, Any]]

    timestamp: datetime

    class Config:
        from_attributes = True