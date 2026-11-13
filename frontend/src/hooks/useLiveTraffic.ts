import { useQuery } from "@tanstack/react-query";
import {
  getLiveTraffic,
  getLivePrediction,
  getTrafficEvents,
  getLiveIncidents,
  getTomTomOverview,
  type TrafficEventsParams,
} from "../api/liveTraffic";

export function useLiveTraffic(options?: { pollingEnabled?: boolean }) {
  const pollingEnabled = options?.pollingEnabled ?? true;
  return useQuery({
    queryKey: ["live-traffic"],
    queryFn: ({ signal }) => getLiveTraffic(signal),
    refetchInterval: pollingEnabled ? 5000 : false,
    refetchIntervalInBackground: false,
    retry: 1,
    refetchOnWindowFocus: false,
  });
}

export function useLiveIncidents() {
  return useQuery({
    queryKey: ["live-incidents"],
    queryFn: ({ signal }) => getLiveIncidents(signal),
    refetchInterval: 30000,
    refetchIntervalInBackground: false,
    retry: 1,
    refetchOnWindowFocus: false,
  });
}

export function useTomTomOverview() {
  return useQuery({
    queryKey: ["tomtom-overview"],
    queryFn: ({ signal }) => getTomTomOverview(signal),
    refetchInterval: 30000,
    refetchIntervalInBackground: false,
    retry: 1,
    refetchOnWindowFocus: false,
  });
}

export function useLivePrediction() {
  return useQuery({
    queryKey: ["live-prediction"],
    queryFn: ({ signal }) => getLivePrediction(signal),
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
    retry: 1,
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

