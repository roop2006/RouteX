import { useQuery } from "@tanstack/react-query";
import { getLiveTraffic, getLivePrediction, getTrafficEvents, type TrafficEventsParams } from "../api/liveTraffic";

export function useLiveTraffic(options?: { pollingEnabled?: boolean }) {
  const pollingEnabled = options?.pollingEnabled ?? true;
  return useQuery({
    queryKey: ["live-traffic"],
    queryFn: getLiveTraffic,
    refetchInterval: pollingEnabled ? 5000 : false,
    refetchIntervalInBackground: false,
  });
}

export function useLivePrediction() {
  return useQuery({
    queryKey: ["live-prediction"],
    queryFn: getLivePrediction,
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  });
}

export function useTrafficEvents(params?: TrafficEventsParams) {
  return useQuery({
    queryKey: ["traffic-events", params],
    queryFn: () => getTrafficEvents(params),
    refetchInterval: 10000,
    refetchIntervalInBackground: false,
  });
}

