export type AlertSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type AlertStatus = "ACTIVE" | "ACKNOWLEDGED" | "RESOLVED";

export interface TrafficAlert {
  id: number;
  rule_key: string;
  category: string;
  severity: AlertSeverity;
  title: string;
  description: string;
  source: string;
  source_event_id: string | null;
  road_id: string | null;
  road_name: string | null;
  intersection_id: string | null;
  latitude: number | null;
  longitude: number | null;
  route_id: string | null;
  status: AlertStatus;
  details: Record<string, unknown>;
  source_timestamp: string | null;
  created_at: string;
  updated_at: string;
  last_seen_at: string;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
}

export interface RouteTrafficAlert {
  route_id?: string;
  marker_latitude?: number | null;
  marker_longitude?: number | null;
  alert: TrafficAlert;
  distance_along_route_meters: number | null;
  distance_to_route_meters: number | null;
}

export interface RouteAlertSnapshot {
  route_id: string;
  status: "AVAILABLE" | "STALE" | "UNAVAILABLE" | "NOT_CONFIGURED";
  checked_at: string | null;
  freshness?: string;
  error: string | null;
  incident_count: number;
  incidents: import("./traffic").TrafficIncident[];
  alerts: RouteTrafficAlert[];
}

export interface AlertRule {
  rule_key: string;
  name: string;
  category: string;
  enabled: boolean;
  severity: AlertSeverity;
  cooldown_seconds: number;
  thresholds: Record<string, unknown>;
}

export interface AlertNotification {
  id: number;
  alert_id: number;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
  read_at: string | null;
}

export interface AlertNotificationList {
  unread_count: number;
  notifications: AlertNotification[];
}

export interface AlertStatistics {
  active: number;
  acknowledged: number;
  resolved: number;
  unread_notifications: number;
  by_severity: Record<string, number>;
  by_category: Record<string, number>;
}
