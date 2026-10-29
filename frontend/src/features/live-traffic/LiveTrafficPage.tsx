import React, { useState } from "react";
import {
  Activity,
  Car,
  Gauge,
  Clock,
  Play,
  Pause,
  RotateCw,
  Compass,
  Layers,
  Camera,
  AlertTriangle,
} from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { MetricCard } from "../../components/dashboard/MetricCard";
import { VehicleDistribution } from "../../components/dashboard/VehicleDistribution";
import { LoadingState } from "../../components/common/LoadingState";
import { ErrorState } from "../../components/common/ErrorState";
import { EmptyState } from "../../components/common/EmptyState";
import { useLiveTraffic } from "../../hooks/useLiveTraffic";
import { formatDensity, formatSpeed, formatTimestamp, formatTimeOnly } from "../../utils/formatters";
import { getCongestionBadgeClass } from "../../utils/congestion";

export const LiveTrafficPage: React.FC = () => {
  const [isPollingPaused, setIsPollingPaused] = useState(false);

  const {
    data: liveTraffic,
    isLoading,
    isFetching,
    error,
    refetch,
    dataUpdatedAt,
  } = useLiveTraffic({ pollingEnabled: !isPollingPaused });

  const handleTogglePolling = () => {
    setIsPollingPaused((prev) => !prev);
  };

  const laneCounts = liveTraffic?.lane_counts || {};
  const directionCounts = liveTraffic?.direction_counts || {};
  const congestion = liveTraffic?.congestion_level || "UNKNOWN";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Live Traffic Telemetry"
        subtitle="Active sensor snapshots retrieved from Redis state store"
        badge={
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            Telemetry Active
          </span>
        }
        actions={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleTogglePolling}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                isPollingPaused
                  ? "bg-amber-600/20 text-amber-300 border-amber-500/40 hover:bg-amber-600/30"
                  : "bg-slate-800 text-slate-300 border-slate-700 hover:text-white"
              }`}
            >
              {isPollingPaused ? (
                <>
                  <Play className="w-3.5 h-3.5" />
                  <span>Resume Auto-Poll</span>
                </>
              ) : (
                <>
                  <Pause className="w-3.5 h-3.5" />
                  <span>Pause Polling</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => refetch()}
              disabled={isFetching}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors disabled:opacity-50"
            >
              <RotateCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} />
              <span>Poll Now</span>
            </button>
          </div>
        }
      />

      {/* Stream Architecture Clarification Banner */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-xs text-slate-400 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-blue-400 flex-shrink-0" />
          <span>
            <strong className="text-slate-200">Sampling Protocol:</strong> High-frequency snapshot polled from Redis key{" "}
            <code className="text-slate-300 bg-slate-800 px-1.5 py-0.5 rounded">routex:traffic:latest</code> (5-second cadence).
          </span>
        </div>
        <div className="flex items-center gap-3 font-mono text-[11px] text-slate-400">
          <span>Last Updated: {dataUpdatedAt ? formatTimeOnly(new Date(dataUpdatedAt).toISOString()) : "N/A"}</span>
          {isFetching && <span className="text-blue-400 animate-pulse">Syncing...</span>}
        </div>
      </div>

      {isLoading ? (
        <LoadingState message="Connecting to live Redis traffic buffer..." skeletonLines={4} />
      ) : error ? (
        <ErrorState
          title="Live Traffic Stream Unavailable"
          error={error}
          message="Unable to fetch live traffic snapshot from the backend. The Redis cache may be empty or unpopulated."
          onRetry={() => refetch()}
        />
      ) : !liveTraffic ? (
        <EmptyState
          title="No Live Traffic Data"
          description="Redis currently has no active traffic data published by the computer vision or Kafka streaming workers."
        />
      ) : (
        <div className="space-y-6">
          {/* Stale Data Notice */}
          {(isPollingPaused ||
            (liveTraffic.timestamp &&
              dataUpdatedAt > 0 &&
              dataUpdatedAt - new Date(liveTraffic.timestamp).getTime() > 5 * 60 * 1000)) && (
            <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-4 text-xs text-amber-200 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="font-semibold text-amber-100">
                  {isPollingPaused ? "Polling Paused (Cached State)" : "Historical Telemetry Snapshot (Stale Buffer)"}
                </p>
                <p className="text-amber-300/90 leading-relaxed">
                  {isPollingPaused
                    ? "Automatic polling is currently paused. The telemetry cards below show the state captured before pausing."
                    : `This telemetry snapshot was captured on ${formatTimestamp(liveTraffic.timestamp)}. Upstream optical/streaming workers are not actively injecting newer frames into Redis at this moment.`}
                </p>
              </div>
            </div>
          )}

          {/* Main KPI metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              title="Vehicles in Field"
              value={liveTraffic.total_vehicles}
              subtitle="Current camera frame count"
              icon={<Car className="w-5 h-5 text-blue-400" />}
              accentColor="blue"
            />

            <MetricCard
              title="Congestion Level"
              value={congestion}
              subtitle={`Density: ${formatDensity(liveTraffic.density ?? 0)}`}
              icon={<Activity className="w-5 h-5 text-amber-400" />}
              accentColor={congestion === "HIGH" ? "rose" : congestion === "MEDIUM" ? "amber" : "emerald"}
              badge={
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${getCongestionBadgeClass(congestion)}`}>
                  {congestion}
                </span>
              }
            />

            <MetricCard
              title="Mean Velocity"
              value={formatSpeed(liveTraffic.average_speed ?? 0)}
              subtitle="Calculated over active tracks"
              icon={<Gauge className="w-5 h-5 text-emerald-400" />}
              accentColor="emerald"
            />

            <MetricCard
              title="Observation Time"
              value={formatTimeOnly(liveTraffic.timestamp)}
              subtitle={liveTraffic.timestamp ? new Date(liveTraffic.timestamp).toLocaleDateString() : "Live buffer"}
              icon={<Clock className="w-5 h-5 text-purple-400" />}
              accentColor="purple"
            />
          </div>

          {/* Detailed Sensor & Camera Telemetry Panel */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              {/* Categorization & Vehicle Types */}
              <VehicleDistribution
                vehicleTypes={liveTraffic.vehicle_types}
                title="Active Frame Vehicle Breakdown"
              />

              {/* Lane & Direction Flow Breakdown */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Lane Counts */}
                <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm">
                  <div className="flex items-center gap-2 mb-3">
                    <Layers className="w-4 h-4 text-blue-400" />
                    <h3 className="text-sm font-semibold text-white">Lane Volume Breakdown</h3>
                  </div>
                  {Object.keys(laneCounts).length === 0 ? (
                    <p className="text-xs text-slate-400">No lane distribution recorded in this frame.</p>
                  ) : (
                    <div className="space-y-2">
                      {Object.entries(laneCounts).map(([lane, count]) => (
                        <div
                          key={lane}
                          className="flex items-center justify-between p-2 rounded bg-slate-800/40 border border-slate-800/80 text-xs"
                        >
                          <span className="font-medium text-slate-300 uppercase tracking-wider">{lane}</span>
                          <span className="font-mono font-bold text-white">{count} vehicles</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Direction Counts */}
                <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm">
                  <div className="flex items-center gap-2 mb-3">
                    <Compass className="w-4 h-4 text-indigo-400" />
                    <h3 className="text-sm font-semibold text-white">Direction Flow</h3>
                  </div>
                  {Object.keys(directionCounts).length === 0 ? (
                    <p className="text-xs text-slate-400">No direction vectors recorded in this frame.</p>
                  ) : (
                    <div className="space-y-2">
                      {Object.entries(directionCounts).map(([direction, count]) => (
                        <div
                          key={direction}
                          className="flex items-center justify-between p-2 rounded bg-slate-800/40 border border-slate-800/80 text-xs"
                        >
                          <span className="font-medium text-slate-300 capitalize">{direction.replace(/_/g, " ")}</span>
                          <span className="font-mono font-bold text-white">{count} vehicles</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Right Column: Sensor Metadata */}
            <div className="space-y-6">
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm space-y-4">
                <h3 className="text-sm font-semibold text-white border-b border-slate-800 pb-3 flex items-center gap-2">
                  <Camera className="w-4 h-4 text-emerald-400" />
                  <span>Optical Sensor Metadata</span>
                </h3>

                <div className="space-y-3 text-xs">
                  <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                    <span className="text-slate-400">Camera ID</span>
                    <span className="font-mono font-bold text-white">{liveTraffic.camera_id || "CAM_001"}</span>
                  </div>

                  <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                    <span className="text-slate-400">Intersection</span>
                    <span className="font-mono font-bold text-indigo-300">{liveTraffic.intersection_id || "INT_001"}</span>
                  </div>

                  <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                    <span className="text-slate-400">Coordinates</span>
                    <span className="font-mono text-slate-200">
                      {liveTraffic.latitude !== undefined && liveTraffic.longitude !== undefined
                        ? `${liveTraffic.latitude.toFixed(4)}, ${liveTraffic.longitude.toFixed(4)}`
                        : "PostGIS bound"}
                    </span>
                  </div>

                  <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                    <span className="text-slate-400">Events in Frame</span>
                    <span className="font-mono text-slate-200">{liveTraffic.events?.length ?? 0} incidents</span>
                  </div>

                  <div className="flex items-center justify-between py-1">
                    <span className="text-slate-400">Full Timestamp</span>
                    <span className="font-mono text-[11px] text-slate-300">
                      {formatTimestamp(liveTraffic.timestamp)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
