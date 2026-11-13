from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


AlertSeverity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
AlertStatus = Literal["ACTIVE", "ACKNOWLEDGED", "RESOLVED"]


class AlertEventInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str = Field(min_length=2, max_length=100)
    source_event_id: str | None = Field(default=None, max_length=160)
    timestamp: datetime | None = None
    intersection_id: str | None = Field(default=None, max_length=80)
    road_id: str | None = Field(default=None, max_length=80)
    road_name: str | None = Field(default=None, max_length=200)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    total_vehicles: int | None = Field(default=None, ge=0)
    average_speed: float | None = Field(default=None, ge=0)
    free_flow_speed: float | None = Field(default=None, ge=0)
    density: float | None = Field(default=None, ge=0, le=1)
    congestion_level: str | None = None
    delay_seconds: float | None = Field(default=None, ge=0)
    road_closure: bool = False
    predicted_congestion: str | None = None
    anomaly_detected: bool = False
    events: list[dict[str, Any]] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_source_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        events = data.get("events")
        if isinstance(events, dict):
            events = [events]
        elif not isinstance(events, list):
            events = []
        data["events"] = [event for event in events if isinstance(event, dict)]
        if not data.get("source"):
            data["source"] = (
                data.get("provider")
                or data.get("camera_id")
                or next((event.get("source") for event in data["events"] if event.get("source")), None)
            )
        if not data.get("timestamp"):
            data["timestamp"] = next(
                (event.get("timestamp") or event.get("ingested_at") for event in data["events"] if event.get("timestamp") or event.get("ingested_at")),
                None,
            )
        return data

    @model_validator(mode="after")
    def coordinates_are_paired(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self

    @field_validator("source")
    @classmethod
    def source_is_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("source must not be blank")
        return value

    @field_validator("timestamp")
    @classmethod
    def timestamp_not_in_future(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        now = datetime.now(timezone.utc)
        # Naive values are emitted by existing local services; interpret those in
        # the server's local timezone before persisting a consistent UTC value.
        comparable = value.astimezone(timezone.utc)
        if (comparable - now).total_seconds() > 300:
            raise ValueError("timestamp cannot be more than five minutes in the future")
        return comparable.replace(tzinfo=None)


class AlertRuleRead(BaseModel):
    rule_key: str
    name: str
    category: str
    enabled: bool
    severity: AlertSeverity
    cooldown_seconds: int
    thresholds: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class AlertRuleUpdate(BaseModel):
    enabled: bool | None = None
    severity: AlertSeverity | None = None
    cooldown_seconds: int | None = Field(default=None, ge=0, le=86400)
    thresholds: dict[str, Any] | None = None


class TrafficAlertRead(BaseModel):
    id: int
    rule_key: str
    category: str
    severity: AlertSeverity
    title: str
    description: str
    source: str
    source_event_id: str | None
    road_id: str | None
    road_name: str | None
    intersection_id: str | None
    latitude: float | None
    longitude: float | None
    route_id: str | None
    status: AlertStatus
    details: dict[str, Any]
    source_timestamp: datetime | None
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    resolved_at: datetime | None
    resolved_by: str | None

    model_config = ConfigDict(from_attributes=True)


class RouteAlertSearch(BaseModel):
    route_id: str = Field(min_length=1, max_length=80)
    geometry: dict[str, Any]
    corridor_meters: int = Field(default=350, ge=25, le=1000)


class RouteTrafficAlertRead(BaseModel):
    alert: TrafficAlertRead
    distance_along_route_meters: float | None = None
    distance_to_route_meters: float | None = None


class AlertNotificationRead(BaseModel):
    id: int
    alert_id: int
    title: str
    message: str
    is_read: bool
    created_at: datetime
    read_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AlertNotificationList(BaseModel):
    unread_count: int
    notifications: list[AlertNotificationRead]


class AlertStatistics(BaseModel):
    active: int
    acknowledged: int
    resolved: int
    unread_notifications: int
    by_severity: dict[str, int]
    by_category: dict[str, int]
