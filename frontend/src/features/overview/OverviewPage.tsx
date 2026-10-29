import React from "react";
import { Link } from "react-router-dom";
import {
  Car,
  Activity,
  Gauge,
  Sparkles,
  Network,
  Clock,
  ArrowUpRight,
  ShieldCheck,
  ShieldAlert,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "../../components/layout/PageHeader";
import { MetricCard } from "../../components/dashboard/MetricCard";
import { TrafficChart } from "../../components/dashboard/TrafficChart";
import { VehicleDistribution } from "../../components/dashboard/VehicleDistribution";
import { LoadingState } from "../../components/common/LoadingState";
import { ErrorState } from "../../components/common/ErrorState";
import { useLiveTraffic, useLivePrediction, useTrafficEvents } from "../../hooks/useLiveTraffic";
import { useRoads, useIntersections } from "../../hooks/useGeography";
import { checkBackendConnection } from "../../api/health";
import { formatDensity, formatSpeed, formatTimeOnly } from "../../utils/formatters";
import { getCongestionBadgeClass } from "../../utils/congestion";

export const OverviewPage: React.FC = () => {
  const { data: isBackendHealthy } = useQuery({
    queryKey: ["backend-health-ping"],
    queryFn: checkBackendConnection,
    refetchInterval: 15000,
  });

  const {
    data: liveTraffic,
    isLoading: isLoadingTraffic,
    error: trafficError,
    refetch: refetchTraffic,
    dataUpdatedAt: trafficUpdatedAt,
  } = useLiveTraffic();

  const {
    data: livePrediction,
    isLoading: isLoadingPred,
  } = useLivePrediction();

  const {
    data: trafficEvents = [],
  } = useTrafficEvents({ limit: 20 });

  const { data: roads = [] } = useRoads();
  const { data: intersections = [] } = useIntersections();

  const congestion = liveTraffic?.congestion_level || "UNKNOWN";
  const vehicleCount = liveTraffic?.total_vehicles ?? 0;
  const speed = liveTraffic?.average_speed ?? 0;
  const density = liveTraffic?.density ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Operations Overview"
        subtitle="Real-time traffic telemetry, automated detection metrics, and AI forecast summary"
        actions={
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-slate-900 border border-slate-800 text-slate-300">
              <Clock className="w-3.5 h-3.5 text-blue-400" />
              <span>Telemetry: {trafficUpdatedAt ? formatTimeOnly(new Date(trafficUpdatedAt).toISOString()) : "Connecting..."}</span>
            </span>
            <Link
              to="/live-traffic"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-blue-600 hover:bg-blue-500 transition-colors shadow-sm shadow-blue-500/20"
            >
              <span>Live Monitor</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        }
      />

      {/* Backend Connectivity & Data Freshness Indicator Banner */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex items-center gap-1.5 font-medium">
            {isBackendHealthy ? (
              <span className="flex items-center gap-1.5 text-emerald-400">
                <ShieldCheck className="w-4 h-4" />
                <span>Backend Live (FastAPI :8001)</span>
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-rose-400">
                <ShieldAlert className="w-4 h-4" />
                <span>Backend Offline</span>
              </span>
            )}
          </span>
          <span className="text-slate-700 hidden sm:inline">|</span>
          <span className="text-slate-400 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-blue-400" />
            <span>Telemetry Freshness: <strong className="text-slate-200">{trafficUpdatedAt ? formatTimeOnly(new Date(trafficUpdatedAt).toISOString()) : "Connecting..."}</strong></span>
          </span>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono">
          <span>Active PostGIS: <strong className="text-slate-200">{roads.length} corridors / {intersections.length} junctions</strong></span>
        </div>
      </div>

      {/* KPI Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Current Vehicle Flow"
          value={isLoadingTraffic ? "..." : vehicleCount}
          subtitle={`Across active monitored corridors`}
          icon={<Car className="w-5 h-5 text-blue-400" />}
          accentColor="blue"
          badge={
            <span className="text-xs text-slate-400 font-mono">vehicles</span>
          }
        />

        <MetricCard
          title="Congestion Status"
          value={isLoadingTraffic ? "..." : congestion}
          subtitle={`Density ratio: ${formatDensity(density)}`}
          icon={<Activity className="w-5 h-5 text-amber-400" />}
          accentColor={congestion === "HIGH" ? "rose" : congestion === "MEDIUM" ? "amber" : "emerald"}
          badge={
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${getCongestionBadgeClass(congestion)}`}>
              {congestion}
            </span>
          }
        />

        <MetricCard
          title="Average Speed"
          value={isLoadingTraffic ? "..." : formatSpeed(speed)}
          subtitle="Mean flow velocity"
          icon={<Gauge className="w-5 h-5 text-emerald-400" />}
          accentColor="emerald"
        />

        <MetricCard
          title="Monitored Infrastructure"
          value={`${roads.length} Roads / ${intersections.length} Int`}
          subtitle="Active PostGIS network nodes"
          icon={<Network className="w-5 h-5 text-purple-400" />}
          accentColor="purple"
        />
      </div>

      {trafficError && (
        <ErrorState
          title="Live Traffic Stream Unreachable"
          error={trafficError}
          onRetry={refetchTraffic}
        />
      )}

      {/* Main Charts & Breakdown Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Traffic Volume & Speed Trend */}
          <TrafficChart
            data={trafficEvents}
            title="Recent Traffic Events Chronology"
            subtitle="Observed total vehicles and speed from database stream events"
          />

          {/* AI Live Prediction Summary Card */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm relative overflow-hidden">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800/80">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  <Sparkles className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-white">Live AI Forecast Summary</h3>
                  <p className="text-xs text-slate-400">Next-step congestion and volume projection</p>
                </div>
              </div>
              <Link
                to="/predictions"
                className="text-xs text-blue-400 hover:text-blue-300 font-medium inline-flex items-center gap-1"
              >
                Inference Console <ArrowUpRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {isLoadingPred ? (
              <LoadingState message="Generating AI inference from live stream..." />
            ) : livePrediction ? (
              <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="p-3.5 rounded-lg bg-slate-800/50 border border-slate-800">
                  <span className="text-xs text-slate-400 block">Predicted Congestion</span>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="text-lg font-bold text-white font-mono">
                      {livePrediction.prediction.predicted_congestion}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${getCongestionBadgeClass(livePrediction.prediction.predicted_congestion)}`}>
                      AI Classified
                    </span>
                  </div>
                </div>

                <div className="p-3.5 rounded-lg bg-slate-800/50 border border-slate-800">
                  <span className="text-xs text-slate-400 block">Forecasted Vehicle Count</span>
                  <span className="text-lg font-bold text-white font-mono mt-1 block">
                    {Math.round(livePrediction.prediction.predicted_vehicle_count)} vehicles
                  </span>
                </div>

                <div className="p-3.5 rounded-lg bg-slate-800/50 border border-slate-800">
                  <span className="text-xs text-slate-400 block">Model Confidence</span>
                  <span className="text-lg font-bold text-emerald-400 font-mono mt-1 block">
                    {Math.round(livePrediction.prediction.prediction_confidence * 100)}%
                  </span>
                </div>
              </div>
            ) : (
              <div className="py-4 text-center text-xs text-slate-400">
                Live AI prediction unavailable (awaiting live Redis traffic stream input)
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Vehicle Distribution & Recent Events Table */}
        <div className="space-y-6">
          <VehicleDistribution
            vehicleTypes={liveTraffic?.vehicle_types}
            title="Live Vehicle Categorization"
          />

          {/* Recent Events List */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-white">Latest Traffic Events</h3>
              <Link to="/analysis" className="text-xs text-blue-400 hover:text-blue-300">
                View All
              </Link>
            </div>

            <div className="space-y-2.5">
              {trafficEvents.slice(0, 5).map((event) => (
                <div
                  key={event.id}
                  className="p-3 rounded-lg bg-slate-800/40 border border-slate-800 flex items-center justify-between text-xs"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-white">Event #{event.id}</span>
                      <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${getCongestionBadgeClass(event.congestion_level)}`}>
                        {event.congestion_level}
                      </span>
                    </div>
                    <span className="text-slate-400 block text-[11px] mt-0.5">
                      {formatTimeOnly(event.timestamp)} &bull; {event.total_vehicles} vehicles
                    </span>
                  </div>
                  <span className="font-mono text-slate-300 font-medium">
                    {formatSpeed(event.average_speed)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
