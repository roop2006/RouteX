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
  ShieldAlert,
  MapPin,
} from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { MetricCard } from "../../components/dashboard/MetricCard";
import { VehicleDistribution } from "../../components/dashboard/VehicleDistribution";
import { LoadingState } from "../../components/common/LoadingState";
import { ErrorState } from "../../components/common/ErrorState";
import { EmptyState } from "../../components/common/EmptyState";
import { useLiveTraffic, useLiveIncidents } from "../../hooks/useLiveTraffic";
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

  const {
    data: incidentsData,
    isFetching: isFetchingIncidents,
    error: incidentsError,
    refetch: refetchIncidents,
  } = useLiveIncidents();

  const handleTogglePolling = () => {
    setIsPollingPaused((prev) => !prev);
  };

  const laneCounts = liveTraffic?.lane_counts || {};
  const directionCounts = liveTraffic?.direction_counts || {};
  const congestion = liveTraffic?.congestion_level || "UNKNOWN";
  const isTomTom = liveTraffic?.source === "tomtom_traffic_flow";
  const sourceLabel = isTomTom
    ? liveTraffic?.freshness === "FRESH" ? "TomTom Live Traffic" : "TomTom Cached Snapshot"
    : liveTraffic?.source === "redis_live_stream"
    ? "Redis Live Buffer"
    : liveTraffic?.source === "database_stream_telemetry"
    ? "Database Stream Telemetry"
    : liveTraffic?.source === "video_analysis"
    ? "Video Analysis Ingestion"
    : liveTraffic?.source || "Live Telemetry Feed";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Live Traffic Telemetry"
        subtitle="Active sensor snapshots retrieved from RouteX streaming infrastructure"
        badge={
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            {sourceLabel}
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

      {liveTraffic?.provider_error && (
        <div
          role="status"
          className="rounded-lg border border-amber-500/30 bg-amber-950/20 p-3 text-sm text-amber-200"
        >
          TomTom live flow is unavailable: {liveTraffic.provider_error}
          {liveTraffic.source && liveTraffic.source !== "none" && (
            <span className="text-amber-100/80"> Showing {sourceLabel.toLowerCase()} data.</span>
          )}
        </div>
      )}

      {/* Stream Architecture Clarification Banner */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-xs text-slate-400 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-blue-400 flex-shrink-0" />
          <span>
            <strong className="text-slate-200">Data Source:</strong> {sourceLabel}{" "}
            {liveTraffic?.intersection_id ? `(Sensor ${liveTraffic.intersection_id})` : ""}{" "}
            • Polled on a bounded cadence.
          </span>
        </div>
        <div className="flex items-center gap-3 font-mono text-[11px] text-slate-400">
          <span>Last Updated: {dataUpdatedAt ? formatTimeOnly(new Date(dataUpdatedAt).toISOString()) : "N/A"}</span>
          {isFetching && <span className="text-blue-400 animate-pulse">Syncing...</span>}
        </div>
      </div>

      {isLoading ? (
        <LoadingState message="Connecting to live RouteX traffic telemetry..." skeletonLines={4} />
      ) : error ? (
        <ErrorState
          title="Live Traffic Stream Unavailable"
          error={error}
          onRetry={() => refetch()}
        />
      ) : !liveTraffic || liveTraffic.status === "UNAVAILABLE" ? (
        <EmptyState
          title="No Active Live Traffic Stream"
          description={
            liveTraffic?.message ||
            "No streaming camera is currently publishing live telemetry into Redis or database buffers."
          }
        />
      ) : (
        <div className="space-y-6">
          {/* Stale Data Notice */}
          {(isPollingPaused ||
            liveTraffic.freshness === "STALE" ||
            liveTraffic.freshness === "HISTORICAL" ||
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
              value={liveTraffic.total_vehicles ?? "Unavailable"}
              subtitle="Current camera frame count"
              icon={<Car className="w-5 h-5 text-blue-400" />}
              accentColor="blue"
            />

            <MetricCard
              title="Congestion Level"
              value={congestion}
              subtitle={`Density: ${formatDensity(liveTraffic.density)}`}
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
              value={formatSpeed(liveTraffic.average_speed)}
              subtitle={
                liveTraffic.free_flow_speed
                  ? `Free-flow: ${formatSpeed(liveTraffic.free_flow_speed)}`
                  : "Calculated over active tracks"
              }
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

            {/* Right Column: Sensor Metadata & TomTom Stats */}
            <div className="space-y-6">
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm space-y-4">
                <h3 className="text-sm font-semibold text-white border-b border-slate-800 pb-3 flex items-center gap-2">
                  {isTomTom ? (
                    <Compass className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <Camera className="w-4 h-4 text-emerald-400" />
                  )}
                  <span>{isTomTom ? "TomTom Flow Metadata" : "Optical Sensor Metadata"}</span>
                </h3>

                <div className="space-y-3 text-xs">
                  {isTomTom ? (
                    <>
                      <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                        <span className="text-slate-400">Data Provider</span>
                        <span className="font-mono font-bold text-emerald-400">TomTom Traffic API</span>
                      </div>

                      <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                        <span className="text-slate-400">Road Class</span>
                        <span className="font-mono font-bold text-white">{liveTraffic.frc || "FRC2 (Major Arterial)"}</span>
                      </div>

                      <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                        <span className="text-slate-400">Free-Flow Speed</span>
                        <span className="font-mono text-slate-200">
                          {formatSpeed(liveTraffic.free_flow_speed ?? liveTraffic.average_speed)}
                        </span>
                      </div>

                      <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                        <span className="text-slate-400">Confidence Score</span>
                        <span className="font-mono font-bold text-emerald-400">
                          {Math.round((liveTraffic.confidence ?? 1.0) * 100)}%
                        </span>
                      </div>

                      <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                        <span className="text-slate-400">Segment Delay</span>
                        <span className="font-mono text-amber-300">
                          {liveTraffic.delay_seconds ? `${liveTraffic.delay_seconds}s` : "0s (Nominal)"}
                        </span>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                        <span className="text-slate-400">Camera ID</span>
                        <span className="font-mono font-bold text-white">{liveTraffic.camera_id || "CAM_001"}</span>
                      </div>

                      <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                        <span className="text-slate-400">Intersection</span>
                        <span className="font-mono font-bold text-indigo-300">
                          {liveTraffic.intersection_id || "INT_001"}
                        </span>
                      </div>
                    </>
                  )}

                  <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                    <span className="text-slate-400">Coordinates</span>
                    <span className="font-mono text-slate-200">
                      {liveTraffic.latitude !== undefined && liveTraffic.longitude !== undefined
                        ? `${liveTraffic.latitude.toFixed(4)}, ${liveTraffic.longitude.toFixed(4)}`
                        : "PostGIS bound"}
                    </span>
                  </div>

                  <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                    <span className="text-slate-400">Observation Mode</span>
                    <span className="font-mono text-slate-200">
                      {isTomTom ? "Live Segment Flow" : `${liveTraffic.events?.length ?? 0} optical events`}
                    </span>
                  </div>

                  <div className="flex items-center justify-between py-1">
                    <span className="text-slate-400">Snapshot Timestamp</span>
                    <span className="font-mono text-[11px] text-slate-300">
                      {formatTimestamp(liveTraffic.timestamp)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Live Incidents & Road Disruptions Panel (from TomTom) */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-rose-400" />
                <h3 className="text-sm font-semibold text-white">
                  Chennai Metro Live Incidents & Road Disruptions
                </h3>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span>Provider: TomTom Traffic Incidents API</span>
                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[10px]">
                  {incidentsData?.count ?? 0} active
                </span>
                {isFetchingIncidents && <span className="text-blue-400 animate-pulse text-[11px]">Syncing...</span>}
              </div>
            </div>

            {incidentsError ? (
              <ErrorState
                title="Live Incident Request Failed"
                error={incidentsError}
                onRetry={() => refetchIncidents()}
                className="p-4"
              />
            ) : incidentsData && incidentsData.incidents && incidentsData.incidents.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {incidentsData.incidents.slice(0, 6).map((inc) => (
                  <div
                    key={inc.id}
                    className="p-3.5 rounded-lg border border-slate-800/80 bg-slate-950/40 space-y-2 text-xs hover:border-slate-700/80 transition-colors"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-slate-200 truncate">{inc.category_name}</span>
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          inc.magnitude_of_delay >= 3
                            ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                            : inc.magnitude_of_delay === 2
                            ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                            : "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                        }`}
                      >
                        {inc.magnitude_label}
                      </span>
                    </div>

                    <p className="text-slate-300 text-[11px] leading-relaxed line-clamp-2">
                      {inc.description}
                    </p>

                    {(inc.from_road || inc.to_road) && (
                      <div className="flex items-center gap-1.5 text-[11px] text-slate-400 truncate pt-1 border-t border-slate-800/40">
                        <MapPin className="w-3 h-3 text-slate-500 flex-shrink-0" />
                        <span className="truncate">
                          {inc.from_road} {inc.to_road ? `-> ${inc.to_road}` : ""}
                        </span>
                      </div>
                    )}

                    <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 pt-1">
                      <span>Delay: {Math.round(inc.delay_seconds / 60)} min</span>
                      <span>Length: {Math.round(inc.length_meters)}m</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-6 text-center text-xs text-slate-500">
                No active traffic disruptions or road closures detected in this area.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
