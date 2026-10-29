import React, { useState } from "react";
import {
  History,
  Clock,
  Filter,
  CheckCircle2,
  RotateCw,
  Calculator,
  X,
  Sparkles,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { PageHeader } from "../../components/layout/PageHeader";
import { LoadingState } from "../../components/common/LoadingState";
import { ErrorState } from "../../components/common/ErrorState";
import { EmptyState } from "../../components/common/EmptyState";
import {
  usePredictionHistory,
  usePredictionMetrics,
  useEvaluatePrediction,
  useEvaluateByMatch,
} from "../../hooks/usePredictions";
import { formatTimestamp, formatTimeOnly } from "../../utils/formatters";
import { getCongestionBadgeClass } from "../../utils/congestion";
import type { PredictionHistoryItem } from "../../types/prediction";

export const PredictionHistoryPage: React.FC = () => {
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [evaluatingItem, setEvaluatingItem] = useState<PredictionHistoryItem | null>(null);
  const [actualValueInput, setActualValueInput] = useState<number>(35);
  const [actualCongestionInput, setActualCongestionInput] = useState<string>("MEDIUM");

  // Batch match evaluation state
  const [isMatchModalOpen, setIsMatchModalOpen] = useState(false);
  const [matchActualValue, setMatchActualValue] = useState<number>(40);
  const [matchIntersectionId, setMatchIntersectionId] = useState<string>("INT_001");
  const [matchCongestion, setMatchCongestion] = useState<string>("MEDIUM");
  const [matchTolerance, setMatchTolerance] = useState<number>(30);
  const [matchFeedback, setMatchFeedback] = useState<string | null>(null);

  const {
    data: history = [],
    isLoading,
    error,
    refetch,
    isFetching,
  } = usePredictionHistory({
    evaluation_status: statusFilter === "ALL" ? undefined : statusFilter,
    limit: 100,
  });

  const { data: metrics } = usePredictionMetrics();
  const evaluateMutation = useEvaluatePrediction();
  const evaluateByMatchMutation = useEvaluateByMatch();

  const handleOpenEvaluate = (item: PredictionHistoryItem) => {
    setEvaluatingItem(item);
    setActualValueInput(Math.round(item.predicted_value));
    setActualCongestionInput(item.predicted_congestion || "MEDIUM");
  };

  const handleSubmitEvaluation = (e: React.FormEvent) => {
    e.preventDefault();
    if (!evaluatingItem) return;

    evaluateMutation.mutate(
      {
        predictionId: evaluatingItem.id,
        actual: {
          actual_value: actualValueInput,
          actual_congestion: actualCongestionInput,
        },
      },
      {
        onSuccess: () => {
          setEvaluatingItem(null);
          refetch();
        },
      }
    );
  };

  const handleBatchMatchEvaluation = (e: React.FormEvent) => {
    e.preventDefault();
    setMatchFeedback(null);

    evaluateByMatchMutation.mutate(
      {
        actual_value: matchActualValue,
        intersection_id: matchIntersectionId.trim() || undefined,
        actual_congestion: matchCongestion || undefined,
        tolerance_minutes: matchTolerance,
      },
      {
        onSuccess: (evaluated) => {
          setMatchFeedback(
            evaluated.length > 0
              ? `Successfully matched and evaluated ${evaluated.length} pending prediction(s)!`
              : "No pending predictions found within the specified time window tolerance."
          );
          refetch();
        },
      }
    );
  };

  const evaluatedItems = history.filter(
    (h) => h.evaluation_status === "EVALUATED" && h.actual_value !== null
  );

  const chartData = evaluatedItems.slice(-15).map((h) => ({
    id: `#${h.id}`,
    predicted: Math.round(h.predicted_value),
    actual: Math.round(h.actual_value!),
    error: h.absolute_error !== null ? Number(h.absolute_error.toFixed(1)) : 0,
  }));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Prediction History & Model Evaluation"
        subtitle="Historical ML forecasts, actual observation match tracking, and error evaluation metrics"
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs bg-slate-900 border border-slate-800 rounded-lg p-1">
              <Filter className="w-3.5 h-3.5 text-slate-400 ml-2" />
              <span className="text-slate-400 text-[11px] font-medium mr-1">Status:</span>
              {(["ALL", "PENDING", "EVALUATED"] as const).map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => setStatusFilter(st)}
                  className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                    statusFilter === st
                      ? "bg-blue-600 text-white font-bold"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={() => {
                setIsMatchModalOpen(true);
                setMatchFeedback(null);
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-500 text-white transition-colors shadow-sm shadow-indigo-500/20"
            >
              <Calculator className="w-3.5 h-3.5" />
              <span>Match & Evaluate Batch</span>
            </button>

            <button
              type="button"
              onClick={() => refetch()}
              disabled={isFetching}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
            >
              <RotateCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin text-blue-400" : ""}`} />
              <span>Refresh</span>
            </button>
          </div>
        }
      />

      {/* Model Performance Overview Cards */}
      {metrics && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60">
            <span className="text-[11px] uppercase text-slate-400 font-medium">Evaluated Pairs</span>
            <div className="text-xl font-bold font-mono text-white mt-1">
              {metrics.evaluated_count} / {metrics.total_predictions}
            </div>
            <span className="text-[10px] text-slate-400">matched with ground truth</span>
          </div>

          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60">
            <span className="text-[11px] uppercase text-slate-400 font-medium">Mean Absolute Error</span>
            <div className="text-xl font-bold font-mono text-emerald-400 mt-1">
              {metrics.mae !== null ? `${metrics.mae.toFixed(2)} veh` : "Pending"}
            </div>
            <span className="text-[10px] text-slate-400">average volume delta</span>
          </div>

          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60">
            <span className="text-[11px] uppercase text-slate-400 font-medium">Root Mean Sq Error</span>
            <div className="text-xl font-bold font-mono text-blue-400 mt-1">
              {metrics.rmse !== null ? metrics.rmse.toFixed(2) : "Pending"}
            </div>
            <span className="text-[10px] text-slate-400">standard error penalty</span>
          </div>

          <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60">
            <span className="text-[11px] uppercase text-slate-400 font-medium">Classification Accuracy</span>
            <div className="text-xl font-bold font-mono text-purple-400 mt-1">
              {metrics.classification_accuracy !== null
                ? `${(metrics.classification_accuracy * 100).toFixed(1)}%`
                : "Pending"}
            </div>
            <span className="text-[10px] text-slate-400">congestion level match</span>
          </div>
        </div>
      )}

      {/* Actual vs. Predicted Comparison Chart */}
      {evaluatedItems.length > 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm shadow-lg">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 border-b border-slate-800 pb-3">
            <div>
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-blue-400" />
                <span>Actual vs. Predicted Traffic Volume Comparison</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Ground truth observations compared against model forecasted vehicle volumes (recent evaluated pairs)
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-1 rounded text-xs font-mono font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                {evaluatedItems.length} Evaluated Pairs
              </span>
            </div>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="id" stroke="#64748b" tick={{ fontSize: 11 }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0f172a",
                    borderColor: "#334155",
                    borderRadius: "0.5rem",
                    fontSize: "12px",
                  }}
                  labelStyle={{ color: "#94a3b8" }}
                />
                <Legend wrapperStyle={{ fontSize: "12px", paddingTop: "8px" }} />
                <Bar dataKey="predicted" name="Predicted Vehicles" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="actual" name="Actual Observed" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {isLoading ? (
        <LoadingState message="Fetching prediction audit log..." skeletonLines={5} />
      ) : error ? (
        <ErrorState
          title="Failed to Load Prediction History"
          error={error}
          onRetry={() => refetch()}
        />
      ) : history.length === 0 ? (
        <EmptyState
          title="No Prediction Records Found"
          description={
            statusFilter === "ALL"
              ? "No predictions have been recorded yet. Use the AI Predictions page to generate predictions."
              : `No predictions found matching status "${statusFilter}".`
          }
        />
      ) : (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden backdrop-blur-sm shadow-xl">
          <div className="p-4 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <History className="w-4 h-4 text-blue-400" />
              <h3 className="text-sm font-semibold text-white">Prediction Evaluation Log</h3>
            </div>
            <span className="text-xs text-slate-400 font-mono">
              Showing {history.length} records
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-medium uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3 px-4">ID</th>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Model</th>
                  <th className="py-3 px-4">Predicted Vol</th>
                  <th className="py-3 px-4">Pred Congestion</th>
                  <th className="py-3 px-4">Actual Vol</th>
                  <th className="py-3 px-4">Abs Error</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {history.map((item) => {
                  const isEvaluated = item.evaluation_status === "EVALUATED";

                  return (
                    <tr key={item.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 px-4 font-mono font-medium text-slate-200">#{item.id}</td>
                      <td className="py-3 px-4 font-mono text-slate-400">
                        {formatTimeOnly(item.prediction_timestamp)}
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-300 text-[11px]">
                        {item.model_name.replace("routex_", "")}
                      </td>
                      <td className="py-3 px-4 font-mono font-bold text-white">
                        {Math.round(item.predicted_value)} veh
                      </td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${getCongestionBadgeClass(item.predicted_congestion)}`}>
                          {item.predicted_congestion || "N/A"}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono">
                        {item.actual_value !== null ? (
                          <span className="font-bold text-white">{Math.round(item.actual_value)} veh</span>
                        ) : (
                          <span className="text-slate-500">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 font-mono">
                        {item.absolute_error !== null ? (
                          <span className={item.absolute_error <= 5 ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"}>
                            {item.absolute_error.toFixed(1)}
                          </span>
                        ) : (
                          <span className="text-slate-500">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        {isEvaluated ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            <CheckCircle2 className="w-3 h-3" /> Evaluated
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                            <Clock className="w-3 h-3" /> Pending
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right">
                        {!isEvaluated ? (
                          <button
                            type="button"
                            onClick={() => handleOpenEvaluate(item)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium text-white bg-blue-600/80 hover:bg-blue-600 transition-colors"
                          >
                            <Calculator className="w-3 h-3" />
                            <span>Evaluate</span>
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => handleOpenEvaluate(item)}
                            className="text-xs text-slate-400 hover:text-slate-300"
                          >
                            Re-eval
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Evaluation Modal / Dialog */}
      {evaluatingItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-2xl text-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Calculator className="w-4 h-4 text-blue-400" />
                <span>Evaluate Prediction #{evaluatingItem.id}</span>
              </h3>
              <button
                type="button"
                onClick={() => setEvaluatingItem(null)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 rounded-lg bg-slate-800/50 border border-slate-800 text-[11px] space-y-1 text-slate-300">
              <div className="flex justify-between">
                <span>Predicted Value:</span>
                <span className="font-mono font-bold text-white">{evaluatingItem.predicted_value} vehicles</span>
              </div>
              <div className="flex justify-between">
                <span>Predicted Congestion:</span>
                <span className="font-mono font-bold text-white">{evaluatingItem.predicted_congestion || "N/A"}</span>
              </div>
              <div className="flex justify-between">
                <span>Timestamp:</span>
                <span className="font-mono text-slate-400">{formatTimestamp(evaluatingItem.prediction_timestamp)}</span>
              </div>
            </div>

            <form onSubmit={handleSubmitEvaluation} className="space-y-4">
              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Observed Actual Traffic Volume (Vehicles) *
                </label>
                <input
                  type="number"
                  min="0"
                  step="1"
                  required
                  value={actualValueInput}
                  onChange={(e) => setActualValueInput(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Observed Actual Congestion Level
                </label>
                <select
                  value={actualCongestionInput}
                  onChange={(e) => setActualCongestionInput(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                >
                  <option value="LOW">LOW</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="HIGH">HIGH</option>
                </select>
              </div>

              {evaluateMutation.error && (
                <ErrorState
                  title="Evaluation Submission Failed"
                  error={evaluateMutation.error}
                />
              )}

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setEvaluatingItem(null)}
                  className="px-3 py-2 rounded-lg text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={evaluateMutation.isPending}
                  className="px-4 py-2 rounded-lg text-white font-medium bg-blue-600 hover:bg-blue-500 transition-colors disabled:opacity-50"
                >
                  {evaluateMutation.isPending ? "Recording Error..." : "Save Evaluation"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Batch Match Evaluation Modal */}
      {isMatchModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-2xl text-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Calculator className="w-4 h-4 text-indigo-400" />
                <span>Batch Match & Evaluate Predictions</span>
              </h3>
              <button
                type="button"
                onClick={() => setIsMatchModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-slate-400 leading-relaxed">
              Connects to <code className="text-slate-300 bg-slate-800 px-1 py-0.5 rounded">POST /prediction/evaluate-by-match</code>.
              Finds pending predictions matching the specified intersection and time window tolerance, then computes error against the observed ground truth.
            </p>

            {matchFeedback && (
              <div className="p-3 rounded-lg bg-indigo-950/40 border border-indigo-800/60 text-indigo-200">
                {matchFeedback}
              </div>
            )}

            <form onSubmit={handleBatchMatchEvaluation} className="space-y-4">
              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Observed Actual Traffic Volume (Vehicles) *
                </label>
                <input
                  type="number"
                  min="0"
                  step="1"
                  required
                  value={matchActualValue}
                  onChange={(e) => setMatchActualValue(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-medium mb-1">
                    Intersection ID
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. INT_001 (or leave blank)"
                    value={matchIntersectionId}
                    onChange={(e) => setMatchIntersectionId(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-slate-300 font-medium mb-1">
                    Actual Congestion
                  </label>
                  <select
                    value={matchCongestion}
                    onChange={(e) => setMatchCongestion(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-indigo-500"
                  >
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Time Window Tolerance (Minutes) *
                </label>
                <input
                  type="number"
                  min="1"
                  max="1440"
                  required
                  value={matchTolerance}
                  onChange={(e) => setMatchTolerance(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-indigo-500"
                />
                <span className="text-[10px] text-slate-400 mt-1 block">
                  Predictions within &plusmn;{matchTolerance} minutes of current observation will be evaluated.
                </span>
              </div>

              {evaluateByMatchMutation.error && (
                <ErrorState
                  title="Batch Evaluation Failed"
                  error={evaluateByMatchMutation.error}
                />
              )}

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsMatchModalOpen(false)}
                  className="px-3 py-2 rounded-lg text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700"
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={evaluateByMatchMutation.isPending}
                  className="px-4 py-2 rounded-lg text-white font-medium bg-indigo-600 hover:bg-indigo-500 transition-colors disabled:opacity-50"
                >
                  {evaluateByMatchMutation.isPending ? "Matching & Evaluating..." : "Execute Match Evaluation"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
