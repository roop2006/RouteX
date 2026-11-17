import React, { useMemo, useState } from "react";
import { SelectedRouteContext } from "./selectedRouteContext";
import type { SelectedRouteContextValue } from "./selectedRouteContext";
import type { RouteAlternative, RouteAnalysisResponse } from "../types/userAnalysis";
import { useRouteAlerts } from "../hooks/useAlerts";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";

export const SelectedRouteProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [analysis, setAnalysisResult] = useState<RouteAnalysisResponse | null>(null);
  const [baseRoute, setSelectedRoute] = useState<RouteAlternative | null>(null);
  const telemetry = useQuery({
    queryKey: ["route-telemetry", baseRoute?.route_id, baseRoute?.geometry],
    queryFn: async ({ signal }) => (await apiClient.post<Pick<RouteAlternative, "route_id" | "corridor" | "ai_prediction">>("/live-traffic/route", { route_id: baseRoute!.route_id, geometry: baseRoute!.geometry }, { signal, timeout: 20000 })).data,
    enabled: Boolean(baseRoute),
    initialData: baseRoute ? { route_id: baseRoute.route_id, corridor: baseRoute.corridor, ai_prediction: baseRoute.ai_prediction } : undefined,
    initialDataUpdatedAt: analysis ? new Date(analysis.analyzed_at).getTime() : undefined,
    staleTime: 60000,
    refetchInterval: 60000,
    refetchIntervalInBackground: false,
    retry: false,
  });
  const selectedRoute = useMemo(() => baseRoute && telemetry.data?.route_id === baseRoute.route_id
    ? { ...baseRoute, corridor: telemetry.data.corridor ? { ...telemetry.data.corridor, ...(telemetry.error ? { provider_error: telemetry.error.message, observation_freshness: "STALE" } : {}) } : null, ai_prediction: telemetry.data.ai_prediction }
    : baseRoute, [baseRoute, telemetry.data, telemetry.error]);
  useRouteAlerts(selectedRoute?.route_id ?? null, selectedRoute?.geometry ?? null);

  const value = useMemo<SelectedRouteContextValue>(() => ({
    analysis,
    selectedRoute,
    routeId: selectedRoute?.route_id ?? null,
    origin: analysis?.origin ?? null,
    destination: analysis?.destination ?? null,
    geometry: selectedRoute?.geometry ?? null,
    distanceMeters: selectedRoute?.distance_meters ?? null,
    estimatedTravelTimeSeconds:
      selectedRoute?.traffic_duration_seconds ?? selectedRoute?.free_flow_duration_seconds ?? null,
    calculatedAt: analysis?.analyzed_at ?? null,
    setAnalysis: (result) => {
      setAnalysisResult(result);
      setSelectedRoute(result.selected_route);
    },
    selectAlternative: (route) => setSelectedRoute(route),
    clearRoute: () => {
      setAnalysisResult(null);
      setSelectedRoute(null);
    },
  }), [analysis, selectedRoute]);

  return <SelectedRouteContext.Provider value={value}>{children}</SelectedRouteContext.Provider>;
};
