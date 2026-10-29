import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getPredictionHistory,
  getPredictionMetrics,
  getModelRegistry,
  predictTraffic,
  evaluateSinglePrediction,
  evaluateMatchingPredictions,
  type PredictionHistoryParams,
  type PredictionMetricsParams,
} from "../api/predictions";
import type { TrafficPredictionRequest, MatchEvaluationRequest } from "../types/prediction";

export function usePredictionHistory(params?: PredictionHistoryParams) {
  return useQuery({
    queryKey: ["prediction-history", params],
    queryFn: () => getPredictionHistory(params),
  });
}

export function usePredictionMetrics(params?: PredictionMetricsParams) {
  return useQuery({
    queryKey: ["prediction-metrics", params],
    queryFn: () => getPredictionMetrics(params),
  });
}

export function useModelRegistry() {
  return useQuery({
    queryKey: ["model-registry"],
    queryFn: getModelRegistry,
  });
}

export function usePredictTraffic() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: TrafficPredictionRequest) => predictTraffic(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prediction-history"] });
    },
  });
}

export function useEvaluatePrediction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      predictionId,
      actual,
    }: {
      predictionId: number;
      actual: { actual_value: number; actual_congestion?: string; actual_timestamp?: string };
    }) => evaluateSinglePrediction(predictionId, actual),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prediction-history"] });
      queryClient.invalidateQueries({ queryKey: ["prediction-metrics"] });
    },
  });
}

export function useEvaluateByMatch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: MatchEvaluationRequest) => evaluateMatchingPredictions(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prediction-history"] });
      queryClient.invalidateQueries({ queryKey: ["prediction-metrics"] });
    },
  });
}
