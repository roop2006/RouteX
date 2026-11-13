import { createContext, useContext } from "react";
import type {
  RouteAlternative,
  RouteAnalysisResponse,
  RouteCoordinates,
} from "../types/userAnalysis";

export interface SelectedRouteContextValue {
  analysis: RouteAnalysisResponse | null;
  selectedRoute: RouteAlternative | null;
  routeId: string | null;
  origin: RouteCoordinates | null;
  destination: RouteCoordinates | null;
  geometry: RouteAlternative["geometry"] | null;
  distanceMeters: number | null;
  estimatedTravelTimeSeconds: number | null;
  calculatedAt: string | null;
  setAnalysis: (analysis: RouteAnalysisResponse) => void;
  selectAlternative: (route: RouteAlternative) => void;
  clearRoute: () => void;
}

export const SelectedRouteContext = createContext<SelectedRouteContextValue | null>(null);

export function useSelectedRoute(): SelectedRouteContextValue {
  const context = useContext(SelectedRouteContext);
  if (!context) {
    throw new Error("useSelectedRoute must be used within SelectedRouteProvider");
  }
  return context;
}
