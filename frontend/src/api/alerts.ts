import { apiClient } from "./client";
import type {
  AlertNotification,
  AlertNotificationList,
  AlertRule,
  AlertSeverity,
  AlertStatistics,
  RouteTrafficAlert,
  TrafficAlert,
} from "../types/alerts";

export interface AlertFilters {
  status?: "ACTIVE" | "ACKNOWLEDGED" | "RESOLVED";
  severity?: AlertSeverity;
  category?: string;
  source?: string;
  limit?: number;
  offset?: number;
}

export async function getAlerts(filters: AlertFilters, signal?: AbortSignal): Promise<TrafficAlert[]> {
  const response = await apiClient.get<TrafficAlert[]>("/alerts", { params: filters, signal, timeout: 10000 });
  return response.data;
}

export async function getAlertHistory(signal?: AbortSignal): Promise<TrafficAlert[]> {
  const response = await apiClient.get<TrafficAlert[]>("/alerts/history", { signal, timeout: 10000 });
  return response.data;
}

export async function getRouteAlerts(
  routeId: string,
  geometry: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<RouteTrafficAlert[]> {
  const response = await apiClient.post<RouteTrafficAlert[]>("/alerts/route", {
    route_id: routeId,
    geometry,
  }, { signal, timeout: 10000 });
  return response.data;
}

export async function updateAlert(alertId: number, action: "acknowledge" | "resolve"): Promise<TrafficAlert> {
  const response = await apiClient.post<TrafficAlert>(`/alerts/${alertId}/${action}`, undefined, { timeout: 10000 });
  return response.data;
}

export async function getAlertNotifications(signal?: AbortSignal, includeRead = false): Promise<AlertNotificationList> {
  const response = await apiClient.get<AlertNotificationList>("/alerts/notifications", {
    params: { include_read: includeRead, limit: includeRead ? 100 : 30 }, signal, timeout: 10000,
  });
  return response.data;
}

export async function markAlertNotificationRead(notificationId: number): Promise<AlertNotification> {
  const response = await apiClient.post<AlertNotification>(`/alerts/notifications/${notificationId}/read`, undefined, { timeout: 10000 });
  return response.data;
}

export async function getAlertStatistics(signal?: AbortSignal): Promise<AlertStatistics> {
  const response = await apiClient.get<AlertStatistics>("/alerts/statistics", { signal, timeout: 10000 });
  return response.data;
}

export async function getAlertRules(signal?: AbortSignal): Promise<AlertRule[]> {
  const response = await apiClient.get<AlertRule[]>("/alert-rules", { signal, timeout: 10000 });
  return response.data;
}

export async function patchAlertRule(
  ruleKey: string,
  patch: Partial<Pick<AlertRule, "enabled" | "severity" | "cooldown_seconds" | "thresholds">>,
): Promise<AlertRule> {
  const response = await apiClient.patch<AlertRule>(`/alert-rules/${encodeURIComponent(ruleKey)}`, patch, { timeout: 10000 });
  return response.data;
}
