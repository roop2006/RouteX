import { apiClient } from "./client";
import type { TrafficZone, NearbyTrafficEvent } from "../types/geography";

export async function getZones(): Promise<TrafficZone[]> {
  const response = await apiClient.get<TrafficZone[]>("/geo/zones");
  return response.data;
}

export interface NearbyEventsParams {
  latitude: number;
  longitude: number;
  radius_meters?: number;
}

export async function getNearbyEvents(params: NearbyEventsParams): Promise<NearbyTrafficEvent[]> {
  const response = await apiClient.get<NearbyTrafficEvent[]>("/geo/nearby-events", {
    params,
  });
  return response.data;
}
