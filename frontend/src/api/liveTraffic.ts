import { apiClient } from "./client";
import type { LiveTrafficData, TrafficEvent } from "../types/traffic";
import type { LivePredictionResponse } from "../types/prediction";

export async function getLiveTraffic(): Promise<LiveTrafficData> {
  const response = await apiClient.get<LiveTrafficData>("/live-traffic/");
  return response.data;
}

export async function getLivePrediction(): Promise<LivePredictionResponse> {
  const response = await apiClient.get<LivePredictionResponse>("/ai/live-prediction");
  return response.data;
}

export interface TrafficEventsParams {
  skip?: number;
  limit?: number;
  congestion_level?: string;
}

export async function getTrafficEvents(params?: TrafficEventsParams): Promise<TrafficEvent[]> {
  const response = await apiClient.get<TrafficEvent[]>("/traffic-events/", {
    params,
  });
  return response.data;
}

