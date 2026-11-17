import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSelectedRoute } from "../contexts/selectedRouteContext";
import { useRouteAlerts } from "./useAlerts";
import type { LiveTrafficData } from "../types/traffic";
import {
  getLiveTraffic,
  getLivePrediction,
  getTrafficEvents,
  getLiveIncidents,
  getTomTomOverview,
  type TrafficEventsParams,
} from "../api/liveTraffic";

export function useLiveTraffic(options?: { pollingEnabled?: boolean }) {
  const route = useSelectedRoute();
  const queryClient = useQueryClient();
  const pollingEnabled = options?.pollingEnabled ?? true;
  const query = useQuery({
    queryKey: ["live-traffic"],
    queryFn: ({ signal }) => getLiveTraffic(signal),
    enabled: !route.selectedRoute,
    refetchInterval: pollingEnabled ? 15000 : false,
    refetchIntervalInBackground: false,
    retry: false,
    refetchOnWindowFocus: false,
  });
  const corridor = route.selectedRoute?.corridor;
  if (!route.selectedRoute) return query;
  const data: LiveTrafficData = {
    status: corridor?.telemetry_status === "AVAILABLE" ? "CACHED_STREAM" : "UNAVAILABLE",
    source: "selected_route", message: "Selected route corridor observations", timestamp: corridor?.latest_observation_at ?? undefined,
    freshness: corridor?.observation_freshness, provider_error: corridor?.provider_error,
    total_vehicles: corridor?.observed_total_vehicles ?? null,
    average_speed: corridor?.observed_average_speed, density: corridor?.observed_density,
    congestion_level: corridor?.observed_congestion ?? "UNKNOWN", vehicle_types: {},
    free_flow_speed: corridor?.observed_free_flow_speed ?? undefined,
  };
  return { ...query, data, error: null, isLoading: false, isFetching: false,
    refetch: () => queryClient.refetchQueries({ queryKey: ["route-telemetry", route.routeId] }) };
}

export function useLiveIncidents() {
  const route = useSelectedRoute();
  const routeQuery = useRouteAlerts(route.routeId, route.geometry);
  const query = useQuery({
    queryKey: ["live-incidents"],
    queryFn: ({ signal }) => getLiveIncidents(signal),
    enabled: !route.selectedRoute,
    refetchInterval: 30000,
    refetchIntervalInBackground: false,
    retry: false,
    refetchOnWindowFocus: false,
  });
  if (!route.selectedRoute) return query;
  return { ...routeQuery, data: routeQuery.data ? {
    status: routeQuery.data.status, provider: "TomTom route incidents", count: routeQuery.data.incident_count,
    incidents: routeQuery.data.incidents,
  } : undefined, error: routeQuery.error || (routeQuery.data?.error ? new Error(routeQuery.data.error) : null) };
}

export function useTomTomOverview() {
  return useQuery({
    queryKey: ["tomtom-overview"],
    queryFn: ({ signal }) => getTomTomOverview(signal),
    refetchInterval: 30000,
    refetchIntervalInBackground: false,
    retry: false,
    refetchOnWindowFocus: false,
  });
}

export function useLivePrediction(enabled = true) {
  return useQuery({
    queryKey: ["live-prediction"],
    enabled,
    queryFn: ({ signal }) => getLivePrediction(signal),
    refetchInterval: 15000,
    refetchIntervalInBackground: false,
    retry: false,
    refetchOnWindowFocus: false,
  });
}

export function useTrafficEvents(params?: TrafficEventsParams, enabled = true) {
  return useQuery({
    queryKey: ["traffic-events", params],
    queryFn: ({ signal }) => getTrafficEvents(params, signal),
    refetchInterval: 10000,
    refetchIntervalInBackground: false,
    enabled,
  });
}

