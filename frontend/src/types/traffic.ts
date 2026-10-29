export type CongestionLevel = "LOW" | "MEDIUM" | "HIGH";

export interface LiveTrafficData {
  timestamp?: string;
  total_vehicles: number;
  average_speed?: number;
  density?: number;
  congestion_level?: CongestionLevel | string;
  vehicle_types?: Record<string, number>;
  lane_counts?: Record<string, number>;
  direction_counts?: Record<string, number>;
  events?: Array<Record<string, unknown>>;
  camera_id?: string;
  intersection_id?: string;
  latitude?: number;
  longitude?: number;
}

export interface TrafficEvent {
  id: number;
  total_vehicles: number;
  vehicle_types: Record<string, number>;
  lane_counts: Record<string, number>;
  direction_counts: Record<string, number>;
  average_speed: number;
  density: number;
  congestion_level: CongestionLevel | string;
  events: Array<Record<string, unknown>>;
  timestamp: string;
  intersection_id?: string | null;
  latitude?: number | null;
  longitude?: number | null;
}

export interface TrafficEventCreate {
  total_vehicles: number;
  vehicle_types: Record<string, number>;
  lane_counts: Record<string, number>;
  direction_counts: Record<string, number>;
  average_speed: number;
  density: number;
  congestion_level: CongestionLevel | string;
  events?: Array<Record<string, unknown>>;
  intersection_id?: string;
  latitude?: number;
  longitude?: number;
}

