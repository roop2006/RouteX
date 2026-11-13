import { apiClient } from "./client";
import type { LiveTrafficData, TrafficEvent, TrafficIncident, TomTomCitySnapshot } from "../types/traffic";
import type { LivePredictionResponse } from "../types/prediction";

export async function getLiveTraffic(signal?: AbortSignal): Promise<LiveTrafficData> {
  const response = await apiClient.get<LiveTrafficData>("/live-traffic/", { signal, timeout: 9000 });
  return response.data;
}

export async function getLivePrediction(signal?: AbortSignal): Promise<LivePredictionResponse> {
  const response = await apiClient.get<LivePredictionResponse>("/ai/live-prediction", { signal, timeout: 9000 });
  return response.data;
}

export interface IncidentsResponse {
  status: string;
  provider: string;
  count: number;
  incidents: TrafficIncident[];
}

export async function getLiveIncidents(signal?: AbortSignal): Promise<IncidentsResponse> {
  const response = await apiClient.get<IncidentsResponse>("/live-traffic/incidents", { signal, timeout: 10000 });
  return response.data;
}

export async function getTomTomOverview(signal?: AbortSignal): Promise<TomTomCitySnapshot> {
  const response = await apiClient.get<TomTomCitySnapshot>("/live-traffic/tomtom", { signal, timeout: 12000 });
  return response.data;
}

export interface TrafficEventsParams {
  skip?: number;
  limit?: number;
  congestion_level?: string;
}

export async function getTrafficEvents(params?: TrafficEventsParams, signal?: AbortSignal): Promise<TrafficEvent[]> {
  const response = await apiClient.get<TrafficEvent[]>("/traffic-events/", {
    params,
    signal,
    timeout: 10000,
  });
  return response.data;
}

