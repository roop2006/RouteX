export interface NearbyTrafficEvent {
  id: number;
  intersection_id: string | null;
  total_vehicles: number;
  average_speed: number;
  density: number;
  congestion_level: string;
  latitude: number;
  longitude: number;
  timestamp: string;
}

export interface TrafficZone {
  zone_id: string;
  name: string;
  zone_type: string;
  geometry: string | null;
}

export interface Intersection {
  intersection_id: string;
  name: string;
  latitude: number;
  longitude: number;
  geometry: string | null;
}

export interface RoadSegment {
  road_id: string;
  road_name: string;
  speed_limit: number;
  lanes: number;
  geometry: string | null;
}
