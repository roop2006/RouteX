from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class RouteCoordinates(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude")
    lng: float = Field(..., ge=-180.0, le=180.0, description="Longitude")
    name: Optional[str] = Field(None, description="Optional human-readable label or address")


class RouteAnalysisRequest(BaseModel):
    origin: RouteCoordinates
    destination: RouteCoordinates
    include_alternatives: bool = Field(default=True, description="Whether to include route alternatives")
    mode: str = Field(default="driving", description="Travel mode (driving)")


class RouteAIExplanation(BaseModel):
    status: str  # "AVAILABLE" | "INSUFFICIENT_DATA"
    model_name: Optional[str] = None
    predicted_congestion: Optional[str] = None
    prediction_confidence: Optional[float] = None
    predicted_vehicle_count: Optional[float] = None
    features_used: Optional[dict[str, Any]] = None
    explanation: str


class RouteTrafficObservation(BaseModel):
    id: int
    intersection_id: Optional[str] = None
    latitude: float
    longitude: float
    total_vehicles: int
    vehicle_types: dict[str, float] = Field(default_factory=dict)
    lane_counts: dict[str, float] = Field(default_factory=dict)
    direction_counts: dict[str, float] = Field(default_factory=dict)
    average_speed: float
    free_flow_speed: Optional[float] = None
    density: float
    congestion_level: str
    timestamp: datetime
    source: str
    event_type: Optional[str] = None
    severity: Optional[int] = None
    description: Optional[str] = None
    delay_seconds: Optional[float] = None
    details: dict[str, Any] = Field(default_factory=dict)


class CorridorRoadMatch(BaseModel):
    road_id: str
    road_name: str
    speed_limit: float
    lanes: int
    geometry: Optional[dict[str, Any]] = None
    length_meters: Optional[float] = None
    distance_to_route_meters: Optional[float] = None
    match_relation: str = "NEARBY"
    observed_average_speed: Optional[float] = None
    observed_congestion: Optional[str] = None
    observation_count: int = 0
    last_observation_at: Optional[datetime] = None
    observation_source: Optional[str] = None


class CorridorIntersectionMatch(BaseModel):
    intersection_id: str
    name: str
    latitude: float
    longitude: float
    distance_to_route_meters: Optional[float] = None
    associated_road_ids: list[str] = Field(default_factory=list)
    observed_average_speed: Optional[float] = None
    observed_congestion: Optional[str] = None
    observation_count: int = 0
    last_observation_at: Optional[datetime] = None
    observation_source: Optional[str] = None


class CorridorZoneMatch(BaseModel):
    zone_id: str
    name: str
    zone_type: str


class CorridorDetail(BaseModel):
    matched_roads: list[CorridorRoadMatch]
    nearby_intersections: list[CorridorIntersectionMatch]
    traversed_zones: list[CorridorZoneMatch]
    traffic_observations: list[RouteTrafficObservation] = Field(default_factory=list)
    telemetry_status: str  # "AVAILABLE" | "UNAVAILABLE"
    telemetry_sample_count: int
    observed_average_speed: Optional[float] = None
    observed_free_flow_speed: Optional[float] = None
    observed_total_vehicles: Optional[float] = None
    observed_density: Optional[float] = None
    observed_congestion: Optional[str] = None
    speed_limit_reference: Optional[float] = None
    latest_observation_at: Optional[datetime] = None
    observation_age_seconds: Optional[float] = None
    observation_freshness: str = "UNAVAILABLE"
    active_incidents_count: int = 0
    incident_delay_seconds: float = 0.0
    telemetry_source: Optional[str] = None
    incidents_summary: list[str] = Field(default_factory=list)


class RouteAlternative(BaseModel):
    route_id: str
    summary: str
    distance_meters: float
    distance_km: float
    free_flow_duration_seconds: float
    free_flow_duration_minutes: float
    traffic_duration_seconds: Optional[float] = None
    traffic_duration_minutes: Optional[float] = None
    delay_minutes: Optional[float] = None
    congestion_level: str
    geometry: dict[str, Any]  # GeoJSON LineString
    corridor_data_status: str  # "LIVE_TELEMETRY" | "HISTORICAL_TELEMETRY" | "NO_TELEMETRY"
    corridor: Optional[CorridorDetail] = None
    ai_prediction: Optional[RouteAIExplanation] = None
    rank: int = 1
    is_recommended: bool = False
    recommendation_reason: Optional[str] = None
    incidents_count: int = 0


class RouteAnalysisResponse(BaseModel):
    origin: RouteCoordinates
    destination: RouteCoordinates
    selected_route: RouteAlternative
    alternatives: list[RouteAlternative]
    corridor: CorridorDetail
    ai_prediction: RouteAIExplanation
    analyzed_at: datetime
    data_freshness_note: str
    recommended_route_summary: Optional[str] = None
    recommendation_explanation: Optional[str] = None
    recommendation_basis: Optional[str] = None
    traffic_provider: Optional[str] = "TomTom Traffic API"


# --- Video Analysis Schemas ---

class VideoAnalysisJobResponse(BaseModel):
    job_id: str
    filename: str
    status: str  # "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED" | "CANCELLED"
    message: str
    created_at: datetime


class LocalVideoAnalysisRequest(BaseModel):
    video_path: str = Field(default="data/videos/traffic.mp4", description="Relative or absolute path to video file on server")
    intersection_id: Optional[str] = Field(default="INT_001", description="Associated intersection ID")


class FrameSample(BaseModel):
    second: float
    frame_index: int
    vehicles_in_frame: int
    density: float
    speed: float


class VideoAnalysisResult(BaseModel):
    job_id: str
    filename: str
    total_frames: int
    processed_frames: int = 0
    duration_seconds: float
    fps: float
    total_vehicles_detected: int
    vehicle_types: dict[str, float]
    lane_counts: dict[str, float]
    direction_counts: dict[str, float]
    line_crossing_counts: dict[str, float] = Field(default_factory=dict)
    line_crossing_total: int = 0
    average_speed: float
    density: float
    congestion_level: str
    anomaly_events: list[dict[str, Any]]
    frame_samples: list[FrameSample]
    preview_image_base64: Optional[str] = None
    annotated_video_url: Optional[str] = None
    intersection_id: Optional[str] = None
    ai_prediction: Optional[dict[str, Any]] = None
    processed_at: datetime


class VideoAnalysisStatusResponse(BaseModel):
    job_id: str
    filename: str
    status: str
    progress_percent: float
    current_fps: float
    frames_processed: int
    total_frames: int
    error: Optional[str] = None
    result: Optional[VideoAnalysisResult] = None


# --- Combined & Geocoding Schemas ---

class CombinedAnalysisRequest(BaseModel):
    route_request: RouteAnalysisRequest
    video_job_id: str


class CombinedAnalysisResponse(BaseModel):
    is_associated: bool
    association_reason: str
    route_analysis: RouteAnalysisResponse
    video_analysis: VideoAnalysisResult
    integrated_traffic_summary: dict[str, Any]


class LocationSuggestion(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    source: str  # "DATABASE_INTERSECTION" | "DATABASE_ROAD" | "PRESET_HOTSPOT"
    description: Optional[str] = None
