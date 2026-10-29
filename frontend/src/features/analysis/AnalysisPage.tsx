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

export const AnalysisPage: React.FC = () => {
  const [congestionFilter, setCongestionFilter] = useState<string>("ALL");
  const [limitFilter, setLimitFilter] = useState<number>(50);

  const {
    data: events = [],
    isLoading,
    error,
    refetch,
  } = useTrafficEvents({
    congestion_level: congestionFilter === "ALL" ? undefined : congestionFilter,
    limit: limitFilter,
    skip: 0,
  });

  // Aggregate stats across fetched real events
  const totalRecords = events.length;
  const avgSpeed =
    totalRecords > 0
      ? events.reduce((sum, e) => sum + (e.average_speed || 0), 0) / totalRecords
      : 0;
  const peakVolume =
    totalRecords > 0
      ? Math.max(...events.map((e) => e.total_vehicles || 0))
      : 0;

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
        subtitle="Historical stream events, aggregated volume analytics, and congestion patterns"
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
          title="No Traffic Events Found"
          description={`No events matched congestion level "${congestionFilter}". Try selecting ALL.`}
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
                    <th className="py-3 px-4">Vehicles</th>
                    <th className="py-3 px-4">Congestion</th>
                    <th className="py-3 px-4">Avg Speed</th>
                    <th className="py-3 px-4">Density</th>
                    <th className="py-3 px-4">Intersection</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {events.map((evt) => (
                    <tr key={evt.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 px-4 font-mono font-medium text-slate-200">#{evt.id}</td>
                      <td className="py-3 px-4 font-mono text-slate-400">{formatTimestamp(evt.timestamp)}</td>
                      <td className="py-3 px-4 font-mono font-bold text-white">{evt.total_vehicles}</td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${getCongestionBadgeClass(evt.congestion_level)}`}>
                          {evt.congestion_level}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-300">{formatSpeed(evt.average_speed)}</td>
                      <td className="py-3 px-4 font-mono text-slate-300">{formatDensity(evt.density)}</td>
                      <td className="py-3 px-4 font-mono text-slate-400">{evt.intersection_id || "Unassigned"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
