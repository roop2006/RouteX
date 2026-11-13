import React, { useMemo, useState } from "react";
import { SelectedRouteContext } from "./selectedRouteContext";
import type { SelectedRouteContextValue } from "./selectedRouteContext";
import type { RouteAlternative, RouteAnalysisResponse } from "../types/userAnalysis";

export const SelectedRouteProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [analysis, setAnalysisResult] = useState<RouteAnalysisResponse | null>(null);
  const [selectedRoute, setSelectedRoute] = useState<RouteAlternative | null>(null);

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
