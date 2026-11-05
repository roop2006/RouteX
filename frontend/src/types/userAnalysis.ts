export interface RouteCoordinates {
  lat: number;
  lng: number;
  name?: string | null;
}

export interface RouteAnalysisRequest {
  origin: RouteCoordinates;
  destination: RouteCoordinates;
  include_alternatives?: boolean;
  mode?: string;
}

export interface RouteAlternative {
  summary: string;
  distance_meters: number;
  distance_km: number;
  free_flow_duration_seconds: number;
  free_flow_duration_minutes: number;
  traffic_duration_seconds: number | null;
  traffic_duration_minutes: number | null;
  delay_minutes: number | null;
  congestion_level: "LOW" | "MEDIUM" | "HIGH" | "UNAVAILABLE" | string;
  geometry: {
    type: "LineString";
    coordinates: [number, number][]; // [lng, lat]
  };
  corridor_data_status: "LIVE_TELEMETRY" | "HISTORICAL_TELEMETRY" | "NO_TELEMETRY" | string;
  rank?: number;
  is_recommended?: boolean;
  recommendation_reason?: string | null;
  incidents_count?: number;
}

export interface CorridorRoadMatch {
  road_id: string;
  road_name: string;
  speed_limit: number;
  lanes: number;
}

export interface CorridorIntersectionMatch {
  intersection_id: string;
  name: string;
  latitude: number;
  longitude: number;
}

export interface CorridorZoneMatch {
  zone_id: string;
  name: string;
  zone_type: string;
}

export interface CorridorDetail {
  matched_roads: CorridorRoadMatch[];
  nearby_intersections: CorridorIntersectionMatch[];
  traversed_zones: CorridorZoneMatch[];
  telemetry_status: "AVAILABLE" | "UNAVAILABLE";
  telemetry_sample_count: number;
  observed_average_speed: number | null;
  observed_density: number | null;
  observed_congestion: string | null;
  speed_limit_reference: number | null;
  active_incidents_count?: number;
  incident_delay_seconds?: number;
  telemetry_source?: string | null;
  incidents_summary?: string[];
}

export interface RouteAIExplanation {
  status: "AVAILABLE" | "INSUFFICIENT_DATA";
  model_name?: string | null;
  predicted_congestion?: string | null;
  prediction_confidence?: number | null;
  predicted_vehicle_count?: number | null;
  features_used?: Record<string, unknown> | null;
  explanation: string;
}

export interface RouteAnalysisResponse {
  origin: RouteCoordinates;
  destination: RouteCoordinates;
  selected_route: RouteAlternative;
  alternatives: RouteAlternative[];
  corridor: CorridorDetail;
  ai_prediction: RouteAIExplanation;
  analyzed_at: string;
  data_freshness_note: string;
  recommended_route_summary?: string | null;
  recommendation_explanation?: string | null;
  recommendation_basis?: string | null;
  traffic_provider?: string | null;
}

export interface FrameSample {
  second: number;
  frame_index: number;
  vehicles_in_frame: number;
  density: number;
  speed: number;
}

export interface VideoAnalysisJobResponse {
  job_id: string;
  filename: string;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED" | "CANCELLED";
  message: string;
  created_at: string;
}

export interface VideoAnalysisResult {
  job_id: string;
  filename: string;
  total_frames: number;
  processed_frames?: number;
  duration_seconds: number;
  fps: number;
  total_vehicles_detected: number;
  vehicle_types: Record<string, number>;
  lane_counts: Record<string, number>;
  direction_counts: Record<string, number>;
  line_crossing_counts?: Record<string, number>;
  line_crossing_total?: number;
  average_speed: number;
  density: number;
  congestion_level: string;
  anomaly_events: Array<Record<string, unknown>>;
  frame_samples: FrameSample[];
  preview_image_base64: string | null;
  annotated_video_url?: string | null;
  intersection_id?: string | null;
  ai_prediction?: {
    model_name?: string;
    status?: string;
    reason?: string;
    predicted_congestion?: string;
    prediction_confidence?: number;
    predicted_vehicle_count?: number;
    input_features?: Record<string, unknown>;
    forecast_horizon?: string;
  } | null;
  processed_at: string;
}

export interface VideoAnalysisStatusResponse {
  job_id: string;
  filename: string;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED" | "CANCELLED";
  progress_percent: number;
  current_fps: number;
  frames_processed: number;
  total_frames: number;
  error?: string | null;
  result?: VideoAnalysisResult | null;
}

export interface LocationSuggestion {
  id: string;
  name: string;
  lat: number;
  lng: number;
  source: "DATABASE_INTERSECTION" | "DATABASE_ROAD" | "PRESET_HOTSPOT" | string;
  description?: string | null;
}

export interface CombinedAnalysisRequest {
  route_request: RouteAnalysisRequest;
  video_job_id: string;
}

export interface CombinedAnalysisResponse {
  is_associated: boolean;
  association_reason: string;
  route_analysis: RouteAnalysisResponse;
  video_analysis: VideoAnalysisResult;
  integrated_traffic_summary: {
    corridor_status: string;
    video_vehicles_observed?: number;
    video_measured_speed?: number;
    video_measured_density?: number;
    video_congestion_level?: string;
    combined_ai_confidence?: number | null;
    traffic_note?: string;
    reason?: string;
    advice?: string;
  };
}
