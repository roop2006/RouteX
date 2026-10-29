import { apiClient } from "./client";
import type {
  TrafficPredictionRequest,
  PredictionResponse,
  PredictionHistoryItem,
  EvaluationMetrics,
  ModelRegistryResponse,
  MatchEvaluationRequest,
} from "../types/prediction";

export async function predictTraffic(
  request: TrafficPredictionRequest
): Promise<PredictionResponse> {
  const response = await apiClient.post<PredictionResponse>("/prediction/", request);
  return response.data;
}

export interface PredictionHistoryParams {
  model_name?: string;
  evaluation_status?: string;
  intersection_id?: string;
  skip?: number;
  limit?: number;
}

export async function getPredictionHistory(
  params?: PredictionHistoryParams
): Promise<PredictionHistoryItem[]> {
  const response = await apiClient.get<PredictionHistoryItem[]>("/prediction/history", {
    params,
  });
  return response.data;
}

export interface PredictionMetricsParams {
  model_name?: string;
  forecast_target?: string;
}

export async function getPredictionMetrics(
  params?: PredictionMetricsParams
): Promise<EvaluationMetrics> {
  const response = await apiClient.get<EvaluationMetrics>("/prediction/metrics", {
    params,
  });
  return response.data;
}

export async function getModelRegistry(): Promise<ModelRegistryResponse> {
  const response = await apiClient.get<ModelRegistryResponse>("/prediction/models");
  return response.data;
}

export async function evaluateSinglePrediction(
  predictionId: number,
  actual: { actual_value: number; actual_congestion?: string; actual_timestamp?: string }
): Promise<PredictionHistoryItem> {
  const response = await apiClient.post<PredictionHistoryItem>(
    `/prediction/evaluate/${predictionId}`,
    actual
  );
  return response.data;
}

export async function evaluateMatchingPredictions(
  request: MatchEvaluationRequest
): Promise<PredictionHistoryItem[]> {
  const response = await apiClient.post<PredictionHistoryItem[]>(
    "/prediction/evaluate-by-match",
    request
  );
  return response.data;
}
