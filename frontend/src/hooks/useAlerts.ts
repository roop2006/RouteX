import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getAlertHistory,
  getAlertNotifications,
  getAlertRules,
  getAlertStatistics,
  getAlerts,
  getRouteAlerts,
  markAlertNotificationRead,
  patchAlertRule,
  updateAlert,
  type AlertFilters,
} from "../api/alerts";

export function useAlerts(filters: AlertFilters = {}, enabled = true) {
  return useQuery({
    queryKey: ["alerts", filters],
    queryFn: ({ signal }) => getAlerts(filters, signal),
    enabled,
    refetchInterval: 15000,
    refetchIntervalInBackground: false,
    retry: 1,
  });
}

export function useAlertHistory(enabled = true) {
  return useQuery({
    queryKey: ["alert-history"],
    queryFn: ({ signal }) => getAlertHistory(signal),
    enabled,
    refetchInterval: false,
    retry: 1,
  });
}

export function useRouteAlerts(routeId: string | null, geometry: Record<string, unknown> | null, enabled = true) {
  return useQuery({
    queryKey: ["route-alerts", routeId],
    queryFn: ({ signal }) => getRouteAlerts(routeId!, geometry!, signal),
    enabled: enabled && Boolean(routeId && geometry),
    refetchInterval: 15000,
    refetchIntervalInBackground: false,
    retry: 1,
  });
}

export function useAlertNotifications(includeRead = false) {
  return useQuery({
    queryKey: ["alert-notifications", includeRead],
    queryFn: ({ signal }) => getAlertNotifications(signal, includeRead),
    refetchInterval: includeRead ? false : 20000,
    refetchIntervalInBackground: false,
    retry: 1,
  });
}

export function useAlertStatistics() {
  return useQuery({
    queryKey: ["alert-statistics"],
    queryFn: ({ signal }) => getAlertStatistics(signal),
    refetchInterval: 20000,
    refetchIntervalInBackground: false,
    retry: 1,
  });
}

export function useAlertRules() {
  return useQuery({ queryKey: ["alert-rules"], queryFn: ({ signal }) => getAlertRules(signal), retry: 1 });
}

export function useAlertActions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ alertId, action }: { alertId: number; action: "acknowledge" | "resolve" }) => updateAlert(alertId, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      queryClient.invalidateQueries({ queryKey: ["route-alerts"] });
      queryClient.invalidateQueries({ queryKey: ["alert-history"] });
      queryClient.invalidateQueries({ queryKey: ["alert-statistics"] });
    },
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: markAlertNotificationRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alert-notifications"] });
      queryClient.invalidateQueries({ queryKey: ["alert-statistics"] });
    },
  });
}

export function usePatchAlertRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ruleKey, patch }: { ruleKey: string; patch: Parameters<typeof patchAlertRule>[1] }) => patchAlertRule(ruleKey, patch),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alert-rules"] }),
  });
}
