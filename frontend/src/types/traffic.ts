export type CongestionLevel = "LOW" | "MEDIUM" | "HIGH";

export interface LiveTrafficData {
  timestamp?: string;
  freshness?: "FRESH" | "RECENT" | "CACHED" | "STALE" | "HISTORICAL" | "UNAVAILABLE" | string;
  cache_age_seconds?: number | null;
  total_vehicles: number | null;
  average_speed?: number | null;
  density?: number | null;
  congestion_level?: CongestionLevel | string;
  vehicle_types?: Record<string, number>;
  lane_counts?: Record<string, number>;
  direction_counts?: Record<string, number>;
  events?: Array<Record<string, unknown>>;
  camera_id?: string;
  intersection_id?: string;
  latitude?: number;
  longitude?: number;
  status?: string;
  source?: string;
  message?: string;
  free_flow_speed?: number;
  delay_seconds?: number;
  confidence?: number;
  provider?: string;
  frc?: string;
  road_closure?: boolean;
  provider_error?: string | null;
}

export interface TrafficIncident {
  id: string;
  icon_category: number;
  category_name: string;
  magnitude_of_delay: number;
  magnitude_label: string;
  description: string;
  delay_seconds: number;
  length_meters: number;
  from_road?: string;
  to_road?: string;
  start_time?: string;
  end_time?: string;
  centroid_lat?: number;
  centroid_lng?: number;
  source?: string;
}

export interface TomTomCitySnapshot {
  status: string;
  provider: string;
  timestamp: string;
  intersections_monitored: number;
  average_speed: number | null;
  average_density: number | null;
  total_delay_seconds: number;
  active_incidents_count: number;
  junctions: Array<{
    intersection_id?: string;
    name?: string;
    latitude: number;
    longitude: number;
    current_speed: number;
    free_flow_speed: number;
    delay_seconds: number;
    congestion_level: string;
    confidence: number;
    frc: string;
  }>;
  incidents: TrafficIncident[];
  message: string;
  provider_error?: string | null;
}

export interface TrafficEvent {
  id: number;
  total_vehicles: number | null;
  vehicle_types: Record<string, number>;
  lane_counts: Record<string, number>;
  direction_counts: Record<string, number>;
  average_speed: number | null;
  density: number | null;
  congestion_level: CongestionLevel | string;
  events: Array<Record<string, unknown>>;
  timestamp: string;
  intersection_id?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  source?: string;
  event_type?: string | null;
  severity?: number | null;
  description?: string | null;
  delay_seconds?: number | null;
}

export interface TrafficEventCreate {
  total_vehicles: number | null;
  vehicle_types: Record<string, number>;
  lane_counts: Record<string, number>;
  direction_counts: Record<string, number>;
  average_speed: number | null;
  density: number | null;
  congestion_level: CongestionLevel | string;
  events?: Array<Record<string, unknown>>;
  intersection_id?: string;
  latitude?: number;
  longitude?: number;
}
