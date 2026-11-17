import React, { useState } from "react";
import { Link } from "react-router-dom";
import {
  Sparkles,
  Send,
  History,
  Layers,
  CheckCircle2,
  AlertCircle,
  Cpu,
} from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { LoadingState } from "../../components/common/LoadingState";
import { ErrorState } from "../../components/common/ErrorState";
import { usePredictTraffic, useModelRegistry, usePredictionMetrics } from "../../hooks/usePredictions";
import { useLivePrediction } from "../../hooks/useLiveTraffic";
import { formatTimestamp, formatTimeOnly } from "../../utils/formatters";
import { getCongestionBadgeClass } from "../../utils/congestion";
import type { TrafficPredictionRequest, PredictionResponse } from "../../types/prediction";
import { useSelectedRoute } from "../../contexts/selectedRouteContext";

export const PredictionsPage: React.FC = () => {
  // Manual Prediction Form State
  const [formData, setFormData] = useState<TrafficPredictionRequest>({
    total_vehicles: 45,
    average_speed: 25.0,
    density: 0.65,
    hour: new Date().getHours(),
    day_of_week: new Date().getDay() === 0 ? 6 : new Date().getDay() - 1, // 0 = Monday
    minute: new Date().getMinutes(),
    intersection_id: "INT_001",
  });

  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [manualResult, setManualResult] = useState<PredictionResponse | null>(null);
  const routeContext = useSelectedRoute();
  const routePrediction = routeContext.selectedRoute?.ai_prediction;

  // Queries & Mutations
  const { data: livePrediction, isLoading: isLoadingLive, error: liveError } = useLivePrediction(!routeContext.selectedRoute);
  const { data: modelRegistry } = useModelRegistry();
  const { data: metrics } = usePredictionMetrics();
  const predictMutation = usePredictTraffic();

  const validateForm = () => {
    const errs: Record<string, string> = {};
    if (formData.total_vehicles < 0) errs.total_vehicles = "Vehicles must be >= 0";
    if (formData.average_speed < 0) errs.average_speed = "Speed must be >= 0";
    if (formData.density < 0 || formData.density > 1) errs.density = "Density must be between 0 and 1";
    if (formData.hour !== undefined && formData.hour !== null && (formData.hour < 0 || formData.hour > 23)) {
      errs.hour = "Hour must be 0-23";
    }
    if (formData.day_of_week !== undefined && formData.day_of_week !== null && (formData.day_of_week < 0 || formData.day_of_week > 6)) {
      errs.day_of_week = "Day must be 0 (Mon) - 6 (Sun)";
    }
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handlePredictSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    predictMutation.mutate(formData, {
      onSuccess: (data) => {
        setManualResult(data);
      },
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Traffic Forecasting"
        subtitle="RouteX ML inference engine: Next-observation congestion classifier and vehicle volume regressor"
        actions={
          <Link
            to="/predictions/history"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
          >
            <History className="w-3.5 h-3.5 text-blue-400" />
            <span>Audit Prediction History</span>
          </Link>
        }
      />

      {/* Aggregate Model Evaluation Metrics Strip */}
      {metrics && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60">
            <span className="text-[11px] font-medium uppercase text-slate-400">Total Recorded</span>
            <div className="text-xl font-bold font-mono text-white mt-1">{metrics.total_predictions}</div>
            <span className="text-[10px] text-slate-400 font-mono">
              {metrics.evaluated_count} evaluated / {metrics.pending_count} pending
            </span>
          </div>

          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60">
            <span className="text-[11px] font-medium uppercase text-slate-400">Mean Abs Error (MAE)</span>
            <div className="text-xl font-bold font-mono text-emerald-400 mt-1">
              {metrics.mae !== null ? metrics.mae.toFixed(2) : "N/A"}
            </div>
            <span className="text-[10px] text-slate-400">vehicles volume error</span>
          </div>

          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60">
            <span className="text-[11px] font-medium uppercase text-slate-400">Root Mean Sq (RMSE)</span>
            <div className="text-xl font-bold font-mono text-blue-400 mt-1">
              {metrics.rmse !== null ? metrics.rmse.toFixed(2) : "N/A"}
            </div>
            <span className="text-[10px] text-slate-400">sample deviation</span>
          </div>

          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60">
            <span className="text-[11px] font-medium uppercase text-slate-400">R² Fit Score</span>
            <div className="text-xl font-bold font-mono text-purple-400 mt-1">
              {metrics.r2 !== null ? `${(metrics.r2 * 100).toFixed(1)}%` : "N/A"}
            </div>
            <span className="text-[10px] text-slate-400">explained variance</span>
          </div>
        </div>
      )}

      {/* Live Continuous Inference Banner */}
      {routeContext.analysis && routeContext.selectedRoute && routePrediction && (
        <section className="rounded-xl border border-purple-500/30 bg-purple-950/20 p-5 space-y-3" aria-label="Selected route AI prediction">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-purple-900/50 pb-3">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-purple-300" />
              <h3 className="text-base font-semibold text-white">Selected Route Prediction</h3>
            </div>
            <span className="text-[11px] text-slate-400">{routeContext.selectedRoute.distance_km} km â€¢ calculated {formatTimeOnly(routeContext.calculatedAt || "")}</span>
          </div>
          <div className="text-xs text-slate-300">
            {routeContext.origin?.name || "Origin"} â†’ {routeContext.destination?.name || "Destination"}
          </div>
          {routePrediction.status === "AVAILABLE" ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div className="p-3 rounded-lg bg-slate-900/70 border border-slate-800"><span className="text-slate-400 block">Predicted congestion</span><strong className="text-white">{routePrediction.predicted_congestion || "Unavailable"}</strong></div>
              <div className="p-3 rounded-lg bg-slate-900/70 border border-slate-800"><span className="text-slate-400 block">Predicted volume</span><strong className="text-white">{routePrediction.predicted_vehicle_count == null ? "Unavailable" : `${Math.round(routePrediction.predicted_vehicle_count)} vehicles`}</strong></div>
              <div className="p-3 rounded-lg bg-slate-900/70 border border-slate-800"><span className="text-slate-400 block">Confidence</span><strong className="text-white">{routePrediction.prediction_confidence == null ? "Unavailable" : `${(routePrediction.prediction_confidence * 100).toFixed(1)}%`}</strong></div>
              <p className="sm:col-span-3 text-slate-400">{routePrediction.explanation}</p>
            </div>
          ) : (
            <p className="text-xs text-amber-300">Route prediction is {routePrediction.status}: {routePrediction.explanation}</p>
          )}
        </section>
      )}

      {/* Live Continuous Inference Banner */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-blue-400" />
            <h3 className="text-base font-semibold text-white">Live Stream Inferred State</h3>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            {livePrediction ? formatTimeOnly(livePrediction.timestamp) : "Polling..."}
          </span>
        </div>

        {isLoadingLive ? (
          <div className="py-6">
            <LoadingState message="Processing live stream inference..." />
          </div>
        ) : liveError ? (
          <div className="py-4 text-xs text-amber-300 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-amber-400" />
            <span>Live prediction unavailable: No live traffic buffer in Redis right now.</span>
          </div>
        ) : livePrediction ? (
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
            <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-800">
              <span className="text-slate-400 block text-[11px]">Inferred Congestion</span>
              <div className="mt-2 flex items-center gap-2">
                <span className="text-xl font-bold text-white font-mono">
                  {livePrediction.prediction.predicted_congestion}
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${getCongestionBadgeClass(livePrediction.prediction.predicted_congestion)}`}>
                  Live Model
                </span>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-800">
              <span className="text-slate-400 block text-[11px]">Forecasted Vehicle Count</span>
              <div className="mt-2 text-xl font-bold font-mono text-white">
                {Math.round(livePrediction.prediction.predicted_vehicle_count)} vehicles
              </div>
            </div>

            <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-800">
              <span className="text-slate-400 block text-[11px]">Model Confidence</span>
              <div className="mt-2 text-xl font-bold font-mono text-emerald-400">
                {Math.round(livePrediction.prediction.prediction_confidence * 100)}%
              </div>
            </div>
          </div>
        ) : null}
      </div>

      {/* Manual Prediction Form & Interactive Simulation */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Form Column */}
        <div className="lg:col-span-3 rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
          <div className="flex items-center gap-2 mb-4 border-b border-slate-800 pb-3">
            <Cpu className="w-4 h-4 text-indigo-400" />
            <h3 className="text-base font-semibold text-white">Manual Model Inference Console</h3>
          </div>

          <form onSubmit={handlePredictSubmit} className="space-y-4 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Total Vehicles *
                </label>
                <input
                  type="number"
                  min="0"
                  value={formData.total_vehicles}
                  onChange={(e) => setFormData({ ...formData, total_vehicles: Number(e.target.value) })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-blue-500"
                />
                {formErrors.total_vehicles && (
                  <p className="text-rose-400 text-[10px] mt-1">{formErrors.total_vehicles}</p>
                )}
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Average Speed (km/h) *
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  value={formData.average_speed}
                  onChange={(e) => setFormData({ ...formData, average_speed: Number(e.target.value) })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-blue-500"
                />
                {formErrors.average_speed && (
                  <p className="text-rose-400 text-[10px] mt-1">{formErrors.average_speed}</p>
                )}
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Density Ratio (0 - 1.0) *
                </label>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                  value={formData.density}
                  onChange={(e) => setFormData({ ...formData, density: Number(e.target.value) })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-blue-500"
                />
                {formErrors.density && (
                  <p className="text-rose-400 text-[10px] mt-1">{formErrors.density}</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Hour of Day (0 - 23)
                </label>
                <input
                  type="number"
                  min="0"
                  max="23"
                  value={formData.hour ?? ""}
                  onChange={(e) => setFormData({ ...formData, hour: e.target.value ? Number(e.target.value) : null })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Day of Week
                </label>
                <select
                  value={formData.day_of_week ?? 0}
                  onChange={(e) => setFormData({ ...formData, day_of_week: Number(e.target.value) })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                >
                  <option value={0}>Monday</option>
                  <option value={1}>Tuesday</option>
                  <option value={2}>Wednesday</option>
                  <option value={3}>Thursday</option>
                  <option value={4}>Friday</option>
                  <option value={5}>Saturday</option>
                  <option value={6}>Sunday</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Intersection ID
                </label>
                <input
                  type="text"
                  value={formData.intersection_id ?? ""}
                  onChange={(e) => setFormData({ ...formData, intersection_id: e.target.value || null })}
                  placeholder="e.g. INT_001"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            {predictMutation.error && (
              <ErrorState
                title="Prediction Execution Failed"
                error={predictMutation.error}
              />
            )}

            <button
              type="submit"
              disabled={predictMutation.isPending}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 transition-colors shadow-lg shadow-blue-600/20 disabled:opacity-50 cursor-pointer"
            >
              <Send className="w-4 h-4" />
              <span>{predictMutation.isPending ? "Evaluating Inference..." : "Run AI Prediction"}</span>
            </button>
          </form>
        </div>

        {/* Prediction Output Result Card */}
        <div className="lg:col-span-2 rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm flex flex-col justify-between">
          <div>
            <h3 className="text-base font-semibold text-white mb-2">Model Prediction Output</h3>
            <p className="text-xs text-slate-400 mb-4">
              Real-time response returned by <code className="text-slate-300">POST /prediction/</code>
            </p>

            {manualResult ? (
              <div className="space-y-4 text-xs">
                <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60 space-y-3">
                  <div>
                    <span className="text-slate-400 text-[10px] uppercase font-semibold">Predicted Congestion</span>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="text-2xl font-bold font-mono text-white">
                        {manualResult.prediction.predicted_congestion}
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${getCongestionBadgeClass(manualResult.prediction.predicted_congestion)}`}>
                        Classification
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-700/60">
                    <div>
                      <span className="text-slate-400 block text-[10px]">Forecast Vehicles</span>
                      <span className="font-mono font-bold text-white text-base">
                        {Math.round(manualResult.prediction.predicted_vehicle_count)}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px]">Confidence</span>
                      <span className="font-mono font-bold text-emerald-400 text-base">
                        {Math.round(manualResult.prediction.prediction_confidence * 100)}%
                      </span>
                    </div>
                  </div>
                </div>

                <div className="text-[11px] text-slate-400 space-y-1">
                  <div className="flex justify-between">
                    <span>Target:</span>
                    <span className="font-mono text-slate-200">total_vehicles & congestion</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Generated Timestamp:</span>
                    <span className="font-mono text-slate-300">{formatTimestamp(manualResult.timestamp)}</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-12 text-center text-xs text-slate-400 space-y-2">
                <Sparkles className="w-8 h-8 text-slate-600 mx-auto" />
                <p>Run the inference form on the left to test the active RouteX Random Forest model.</p>
              </div>
            )}
          </div>

          <div className="pt-4 border-t border-slate-800/80">
            <span className="text-[11px] text-emerald-400 flex items-center gap-1.5 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Predictions automatically recorded into history audit log</span>
            </span>
          </div>
        </div>
      </div>

      {/* Model Registry Reference */}
      {modelRegistry && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm space-y-4">
          <h3 className="text-sm font-semibold text-white border-b border-slate-800 pb-3 flex items-center gap-2">
            <Layers className="w-4 h-4 text-purple-400" />
            <span>Registered Production & External ML Models</span>
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            {modelRegistry.production_models.map((m) => (
              <div key={m.name} className="p-3.5 rounded-lg bg-slate-800/40 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-white font-mono">{m.name}</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30">
                    Production Active
                  </span>
                </div>
                <div className="text-slate-400 text-[11px] space-y-1">
                  <div>Type: <span className="text-slate-300 font-mono">{m.type}</span></div>
                  <div>Target: <span className="text-slate-300 font-mono">{m.target}</span></div>
                  <div>Features: <span className="text-slate-300 font-mono">{m.features_count} inputs</span></div>
                  <div>Domain: <span className="text-slate-300 font-mono">{m.domain}</span></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
