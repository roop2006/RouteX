from datetime import datetime

from pydantic import BaseModel, Field


class TrafficEventCreate(BaseModel):
    vehicle_type: str = Field(min_length=1, max_length=50)
    vehicle_count: int = Field(ge=0)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    congestion_level: str = Field(min_length=1, max_length=20)


class TrafficEventResponse(BaseModel):
    id: int
    vehicle_type: str
    vehicle_count: int
    latitude: float
    longitude: float
    congestion_level: str
    detected_at: datetime

    class Config:
        from_attributes = True