import React, { useState } from "react";
import {
  Filter,
  Car,
  Gauge,
  Layers,
} from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { TrafficChart } from "../../components/dashboard/TrafficChart";
import { VehicleDistribution } from "../../components/dashboard/VehicleDistribution";
import { LoadingState } from "../../components/common/LoadingState";
import { ErrorState } from "../../components/common/ErrorState";
import { EmptyState } from "../../components/common/EmptyState";
import { useTrafficEvents } from "../../hooks/useLiveTraffic";
import { formatSpeed, formatDensity, formatTimestamp } from "../../utils/formatters";
import { getCongestionBadgeClass } from "../../utils/congestion";
import { useSelectedRoute } from "../../contexts/selectedRouteContext";
import type { TrafficEvent } from "../../types/traffic";

export const AnalysisPage: React.FC = () => {
  const [congestionFilter, setCongestionFilter] = useState<string>("ALL");
  const [limitFilter, setLimitFilter] = useState<number>(50);
  const routeContext = useSelectedRoute();
  const routeMode = Boolean(routeContext.analysis && routeContext.selectedRoute);
  const routeCorridor = routeContext.selectedRoute?.corridor || routeContext.analysis?.corridor;

  const {
    data: generalEvents = [],
    isLoading: isLoadingGeneral,
    error: generalError,
    refetch: refetchGeneral,
  } = useTrafficEvents({
    congestion_level: congestionFilter === "ALL" ? undefined : congestionFilter,
    limit: limitFilter,
    skip: 0,
  }, !routeMode);

  const routeEvents: TrafficEvent[] = (routeCorridor?.traffic_observations || []).map((observation) => ({
    id: observation.id,
    intersection_id: observation.intersection_id ?? null,
    latitude: observation.latitude,
    longitude: observation.longitude,
    total_vehicles: observation.total_vehicles,
    vehicle_types: observation.vehicle_types,
    lane_counts: observation.lane_counts,
    direction_counts: observation.direction_counts,
    average_speed: observation.average_speed,
    density: observation.density,
    congestion_level: observation.congestion_level,
    events: [observation.details],
    timestamp: observation.timestamp,
    source: observation.source,
    event_type: observation.event_type,
    severity: observation.severity,
    description: observation.description,
    delay_seconds: observation.delay_seconds,
  }));
  const events = routeMode ? routeEvents : generalEvents;
  const isLoading = !routeMode && isLoadingGeneral;
  const error = !routeMode ? generalError : null;
  const refetch = refetchGeneral;

  // Aggregate stats across fetched real events
  const totalRecords = events.length;
  const measuredSpeeds = events.flatMap(e => e.average_speed == null ? [] : [e.average_speed]);
  const avgSpeed = measuredSpeeds.length ? measuredSpeeds.reduce((a,b) => a+b,0) / measuredSpeeds.length : null;
  const measuredCounts = events.flatMap(e => e.total_vehicles == null ? [] : [e.total_vehicles]);
  const peakVolume = measuredCounts.length ? Math.max(...measuredCounts) : "Unavailable";

  // Aggregate vehicle types across all records
  const aggregatedVehicleTypes: Record<string, number> = {};
  events.forEach((e) => {
    if (e.vehicle_types) {
      Object.entries(e.vehicle_types).forEach(([cat, count]) => {
        aggregatedVehicleTypes[cat] = (aggregatedVehicleTypes[cat] || 0) + count;
      });
    }
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Traffic Flow Analysis"
        subtitle={routeMode
          ? "Traffic observations spatially associated with the selected route corridor"
          : "Historical stream events, aggregated volume analytics, and congestion patterns"}
        actions={
          <div className="flex items-center gap-3">
            {/* Filter by congestion */}
            <div className="flex items-center gap-1.5 text-xs bg-slate-900 border border-slate-800 rounded-lg p-1">
              <Filter className="w-3.5 h-3.5 text-slate-400 ml-2" />
              <span className="text-slate-400 text-[11px] font-medium mr-1">Congestion:</span>
              {(["ALL", "LOW", "MEDIUM", "HIGH"] as const).map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  onClick={() => setCongestionFilter(lvl)}
                  className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                    congestionFilter === lvl
                      ? "bg-blue-600 text-white font-bold"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {lvl}
                </button>
              ))}
            </div>

            {/* Limit selector */}
            <select
              value={limitFilter}
              onChange={(e) => setLimitFilter(Number(e.target.value))}
              className="bg-slate-900 border border-slate-800 text-xs text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-blue-500"
            >
              <option value={25}>25 Events</option>
              <option value={50}>50 Events</option>
              <option value={100}>100 Events</option>
            </select>
          </div>
        }
      />

      {routeMode && routeContext.analysis && routeContext.selectedRoute && routeCorridor && (
        <section className="rounded-xl border border-blue-500/30 bg-blue-950/20 p-4 space-y-3" aria-label="Selected route traffic summary">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-blue-300">Selected route traffic</div>
              <div className="mt-1 text-sm text-white">
                {routeContext.origin?.name || `${routeContext.origin?.lat.toFixed(4)}, ${routeContext.origin?.lng.toFixed(4)}`}
                <span className="mx-2 text-slate-500">â†’</span>
                {routeContext.destination?.name || `${routeContext.destination?.lat.toFixed(4)}, ${routeContext.destination?.lng.toFixed(4)}`}
                <span className="ml-2 text-slate-400">({routeContext.selectedRoute.distance_km} km)</span>
              </div>
            </div>
            <span className="text-xs text-slate-300">
              {routeCorridor.observation_freshness || "UNAVAILABLE"} â€¢ {routeCorridor.telemetry_source || "No observation source"}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div><span className="text-slate-400 block">Congestion</span><strong className="text-white">{routeCorridor.observed_congestion || "UNAVAILABLE"}</strong></div>
            <div><span className="text-slate-400 block">Observed / reference speed</span><strong className="text-white">{routeCorridor.observed_average_speed ?? "â€”"} / {routeCorridor.observed_free_flow_speed ?? routeCorridor.speed_limit_reference ?? "â€”"} km/h</strong><span className="block text-[10px] text-slate-500">Reference uses observed free-flow speed when available, otherwise registered speed limit.</span></div>
            <div><span className="text-slate-400 block">Average volume / density</span><strong className="text-white">{routeCorridor.observed_total_vehicles ?? "â€”"} vehicles / {routeCorridor.observed_density ?? "â€”"}</strong></div>
            <div><span className="text-slate-400 block">Delay / matched observations</span><strong className="text-white">{routeCorridor.incident_delay_seconds ? `${Math.round(routeCorridor.incident_delay_seconds / 60)} min` : "No reported incident delay"} / {routeCorridor.telemetry_sample_count}</strong></div>
          </div>
          {routeCorridor.latest_observation_at && (
            <div className="text-[11px] text-slate-400">Latest observation: {formatTimestamp(routeCorridor.latest_observation_at)} ({Math.round((routeCorridor.observation_age_seconds || 0) / 60)} min ago)</div>
          )}
          {routeContext.selectedRoute.ai_prediction && (
            <div className="border-t border-blue-900/60 pt-3 text-xs text-slate-300">
              Route AI: <strong className="text-white">{routeContext.selectedRoute.ai_prediction.status}</strong>
              {routeContext.selectedRoute.ai_prediction.predicted_congestion && ` â€¢ ${routeContext.selectedRoute.ai_prediction.predicted_congestion}`}
              {routeContext.selectedRoute.ai_prediction.explanation && ` â€¢ ${routeContext.selectedRoute.ai_prediction.explanation}`}
            </div>
          )}
        </section>
      )}

      {/* Aggregate KPI Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center justify-between">
          <div>
            <span className="text-xs uppercase font-medium text-slate-400">Sample Records</span>
            <div className="text-xl font-bold font-mono text-white mt-1">{totalRecords} events</div>
            <span className="text-[11px] text-slate-400">Queried from Postgres</span>
          </div>
          <div className="p-2.5 rounded-lg bg-blue-500/10 text-blue-400">
            <Layers className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center justify-between">
          <div>
            <span className="text-xs uppercase font-medium text-slate-400">Sample Mean Velocity</span>
            <div className="text-xl font-bold font-mono text-emerald-400 mt-1">{formatSpeed(avgSpeed)}</div>
            <span className="text-[11px] text-slate-400">Across filtered batch</span>
          </div>
          <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-400">
            <Gauge className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center justify-between">
          <div>
            <span className="text-xs uppercase font-medium text-slate-400">Peak Volume Recorded</span>
            <div className="text-xl font-bold font-mono text-amber-400 mt-1">{peakVolume} vehicles</div>
            <span className="text-[11px] text-slate-400">Max single event observation</span>
          </div>
          <div className="p-2.5 rounded-lg bg-amber-500/10 text-amber-400">
            <Car className="w-5 h-5" />
          </div>
        </div>
      </div>

      {isLoading ? (
        <LoadingState message="Aggregating historical traffic data..." skeletonLines={5} />
      ) : error ? (
        <ErrorState
          title="Analysis Data Unavailable"
          error={error}
          onRetry={() => refetch()}
        />
      ) : events.length === 0 ? (
        <EmptyState
          title={routeMode ? "No Traffic Observations Along This Route" : "No Traffic Events Found"}
          description={routeMode
            ? "No stored observations fall within the selected route corridor. Route-level infrastructure and traffic metrics remain available when present."
            : `No events matched congestion level "${congestionFilter}". Try selecting ALL.`}
        />
      ) : (
        <div className="space-y-6">
          {/* Chronological Flow Chart */}
          <TrafficChart
            data={events}
            title={`Traffic Chronology (${events.length} observations)`}
            subtitle="Volume and speed variations across registered event timestamps"
          />

          {/* Aggregated Categorization Chart */}
          <VehicleDistribution
            vehicleTypes={aggregatedVehicleTypes}
            title="Cumulative Vehicle Type Breakdown"
          />

          {/* Tabular Event Log */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden backdrop-blur-sm">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white">Event Log Data Table</h3>
              <span className="text-xs text-slate-400 font-mono">Showing {events.length} rows</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-medium uppercase tracking-wider text-[11px]">
                  <tr>
                    <th className="py-3 px-4">ID</th>
                    <th className="py-3 px-4">Timestamp</th>
                    <th className="py-3 px-4">Event / Source</th>
                    <th className="py-3 px-4">Vehicles</th>
                    <th className="py-3 px-4">Congestion</th>
                    <th className="py-3 px-4">Avg Speed</th>
                    <th className="py-3 px-4">Density</th>
                    <th className="py-3 px-4">Location</th>
                    <th className="py-3 px-4">Severity / Delay</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {events.map((evt) => {
                    const detail = evt.events.find((entry) => entry && typeof entry === "object") || {};
                    return (
                      <tr key={evt.id} className="hover:bg-slate-800/30 transition-colors">
                        <td className="py-3 px-4 font-mono font-medium text-slate-200">#{evt.id}</td>
                        <td className="py-3 px-4 font-mono text-slate-400">{formatTimestamp(evt.timestamp)}</td>
                        <td className="py-3 px-4 text-slate-300">
                          <span className="block">{evt.event_type || String(detail.category_name || detail.event_type || "Traffic observation")}</span>
                          <span className="text-[10px] text-slate-500">{evt.source || String(detail.source || "RouteX Telemetry")}</span>
                          {evt.description && <span className="block max-w-xs truncate text-[10px] text-slate-400">{evt.description}</span>}
                        </td>
                        <td className="py-3 px-4 font-mono font-bold text-white">{evt.total_vehicles ?? "Unavailable"}</td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${getCongestionBadgeClass(evt.congestion_level)}`}>
                            {evt.congestion_level}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-slate-300">{formatSpeed(evt.average_speed)}</td>
                        <td className="py-3 px-4 font-mono text-slate-300">{formatDensity(evt.density)}</td>
                        <td className="py-3 px-4 font-mono text-slate-400">{evt.latitude?.toFixed(4)}, {evt.longitude?.toFixed(4)}{evt.intersection_id ? ` (${evt.intersection_id})` : ""}</td>
                        <td className="py-3 px-4 font-mono text-slate-400">{evt.severity == null ? "—" : `M${evt.severity}`}{evt.delay_seconds ? ` / ${Math.round(evt.delay_seconds / 60)} min` : ""}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
