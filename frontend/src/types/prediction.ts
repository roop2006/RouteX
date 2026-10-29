import type { LiveTrafficData } from "./traffic";

export interface TrafficPredictionRequest {
  total_vehicles: number;
  average_speed: number;
  density: number;
  hour?: number | null;
  day_of_week?: number | null;
  minute?: number | null;
  intersection_id?: string | null;
}

export interface MatchEvaluationRequest {
  actual_value: number;
  intersection_id?: string | null;
  actual_congestion?: string | null;
  actual_timestamp?: string | null;
  tolerance_minutes?: number;
}

export interface PredictionResult {
  predicted_congestion: "LOW" | "MEDIUM" | "HIGH" | string;
  prediction_confidence: number;
  predicted_vehicle_count: number;
}

export interface PredictionResponse {
  input: {
    total_vehicles: number;
    average_speed: number;
    density: number;
    hour: number;
    day_of_week: number;
    minute: number;
  };
  prediction: PredictionResult;
  timestamp: string;
}

export interface LivePredictionResponse {
  traffic_data: LiveTrafficData;
  prediction: PredictionResult;
  timestamp: string;
}

export interface PredictionHistoryItem {
  id: number;
  prediction_timestamp: string;
  model_name: string;
  model_version: string;
  forecast_target: string;
  forecast_horizon: string;
  predicted_value: number;
  predicted_congestion: string | null;
  prediction_confidence: number | null;
  actual_value: number | null;
  actual_congestion: string | null;
  actual_timestamp: string | null;
  evaluation_status: string;
  absolute_error: number | null;
  squared_error: number | null;
  intersection_id: string | null;
  input_features: Record<string, unknown> | null;
}

export interface EvaluationMetrics {
  model_name: string;
  forecast_target: string;
  total_predictions: number;
  pending_count: number;
  evaluated_count: number;
  mae: number | null;
  rmse: number | null;
  r2: number | null;
  classification_accuracy: number | null;
}

export interface ModelInfo {
  name: string;
  type: string;
  target: string;
  artifact_path: string;
  features_count: number;
  status: string;
  domain: string;
  metadata_path?: string;
  integration_boundary?: string;
}

export interface ModelRegistryResponse {
  production_models: ModelInfo[];
  external_models: ModelInfo[];
}
