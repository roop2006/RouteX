import { useQuery } from "@tanstack/react-query";
import { getRoads } from "../api/roads";
import { getIntersections } from "../api/intersections";
import { getZones, getNearbyEvents, type NearbyEventsParams } from "../api/geography";

export function useRoads() {
  return useQuery({
    queryKey: ["roads"],
    queryFn: getRoads,
    staleTime: 60000,
  });
}

export function useIntersections() {
  return useQuery({
    queryKey: ["intersections"],
    queryFn: getIntersections,
    staleTime: 60000,
  });
}

export function useZones() {
  return useQuery({
    queryKey: ["zones"],
    queryFn: getZones,
    staleTime: 60000,
  });
}

export function useNearbyEvents(params: NearbyEventsParams, enabled = true) {
  return useQuery({
    queryKey: ["nearby-events", params],
    queryFn: () => getNearbyEvents(params),
    enabled: enabled && !isNaN(params.latitude) && !isNaN(params.longitude),
    refetchInterval: 10000,
  });
}
