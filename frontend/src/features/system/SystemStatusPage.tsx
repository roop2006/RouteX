import React from "react";
import {
  ShieldCheck,
  ShieldAlert,
  RotateCw,
  CheckCircle2,
  HelpCircle,
  Clock,
  AlertTriangle,
  Server,
  Database,
  Layers,
  Cpu,
} from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { useQuery } from "@tanstack/react-query";
import { getBackendHealth } from "../../api/health";
import { getLiveTraffic } from "../../api/liveTraffic";
import { getRoads } from "../../api/roads";
import { getModelRegistry } from "../../api/predictions";
import { formatTimestamp } from "../../utils/formatters";

interface ComponentProbe {
  id: string;
  name: string;
  type: string;
  endpoint: string;
  status: "healthy" | "unhealthy" | "unverified" | "checking";
  latencyMs?: number;
  details: string;
  verifiedDirectly: boolean;
  lastSuccess?: string | null;
  error?: string | null;
}

export const SystemStatusPage: React.FC = () => {
  // Probe FastAPI /health
  const {
    data: fastApiHealth,
    isLoading: isCheckingFastApi,
    error: fastApiError,
    refetch: refetchFastApi,
    dataUpdatedAt: fastApiUpdatedAt,
  } = useQuery({
    queryKey: ["probe-fastapi"],
    queryFn: async () => {
      const start = performance.now();
      const res = await getBackendHealth();
      const latency = Math.round(performance.now() - start);
      return { ...res, latency };
    },
    refetchInterval: 10000,
  });

  // Probe Redis via /live-traffic/
  const {
    data: redisData,
    isLoading: isCheckingRedis,
    error: redisError,
    refetch: refetchRedis,
    dataUpdatedAt: redisUpdatedAt,
  } = useQuery({
    queryKey: ["probe-redis"],
    queryFn: async () => {
      const start = performance.now();
      const data = await getLiveTraffic();
      const latency = Math.round(performance.now() - start);
      return { data, latency };
    },
    refetchInterval: 10000,
    retry: false,
  });

  // Probe PostgreSQL / PostGIS via /roads/
  const {
    data: postgresData,
    isLoading: isCheckingPostgres,
    error: postgresError,
    refetch: refetchPostgres,
    dataUpdatedAt: postgresUpdatedAt,
  } = useQuery({
    queryKey: ["probe-postgres"],
    queryFn: async () => {
      const start = performance.now();
      const data = await getRoads();
      const latency = Math.round(performance.now() - start);
      return { count: data.length, latency };
    },
    refetchInterval: 10000,
    retry: false,
  });

  // Probe ML model registry via /prediction/models
  const {
    data: mlData,
    isLoading: isCheckingML,
    error: mlError,
    refetch: refetchML,
    dataUpdatedAt: mlUpdatedAt,
  } = useQuery({
    queryKey: ["probe-ml"],
    queryFn: async () => {
      const start = performance.now();
      const data = await getModelRegistry();
      const latency = Math.round(performance.now() - start);
      return { models: data.production_models.length, latency };
    },
    refetchInterval: 10000,
    retry: false,
  });

  const handleRefreshAll = () => {
    refetchFastApi();
    refetchRedis();
    refetchPostgres();
    refetchML();
  };

  const probes: ComponentProbe[] = [
    {
      id: "fastapi",
      name: "FastAPI Application Server",
      type: "Core REST Gateway",
      endpoint: "GET /health",
      status: isCheckingFastApi ? "checking" : fastApiHealth?.healthy ? "healthy" : "unhealthy",
      latencyMs: fastApiHealth?.latency,
      details: fastApiHealth?.healthy
        ? "FastAPI responding on localhost:8001"
        : fastApiError
        ? (fastApiError as Error).message
        : "Connection refused or timed out",
      verifiedDirectly: true,
      lastSuccess: fastApiUpdatedAt ? new Date(fastApiUpdatedAt).toISOString() : null,
      error: fastApiError ? (fastApiError as Error).message : null,
    },
    {
      id: "postgres",
      name: "PostgreSQL & PostGIS Database",
      type: "Relational Geospatial Store",
      endpoint: "GET /roads/ (SQL/PostGIS query)",
      status: isCheckingPostgres ? "checking" : !postgresError && postgresData ? "healthy" : "unhealthy",
      latencyMs: postgresData?.latency,
      details: !postgresError
        ? `Spatial query verified (${postgresData?.count ?? 0} road segments verified from database)`
        : "Database connection failed or table inaccessible",
      verifiedDirectly: true,
      lastSuccess: postgresUpdatedAt ? new Date(postgresUpdatedAt).toISOString() : null,
      error: postgresError ? (postgresError as Error).message : null,
    },
    {
      id: "redis",
      name: "Redis Live Traffic Cache",
      type: "In-Memory State Buffer",
      endpoint: "GET /live-traffic/ (redis get_latest)",
      status: isCheckingRedis ? "checking" : !redisError && redisData ? "healthy" : "unhealthy",
      latencyMs: redisData?.latency,
      details: !redisError
        ? "Live traffic buffer operational (telemetry key routex:traffic:latest active)"
        : "Redis service unavailable or no active snapshot published",
      verifiedDirectly: true,
      lastSuccess: redisUpdatedAt ? new Date(redisUpdatedAt).toISOString() : null,
      error: redisError ? (redisError as Error).message : null,
    },
    {
      id: "ml",
      name: "AI Prediction Service",
      type: "RandomForest ML Pipeline",
      endpoint: "GET /prediction/models",
      status: isCheckingML ? "checking" : !mlError && mlData ? "healthy" : "unhealthy",
      latencyMs: mlData?.latency,
      details: !mlError
        ? `Model registry verified (${mlData?.models ?? 0} production artifacts loaded)`
        : "Model artifacts failed to load",
      verifiedDirectly: true,
      lastSuccess: mlUpdatedAt ? new Date(mlUpdatedAt).toISOString() : null,
      error: mlError ? (mlError as Error).message : null,
    },
    {
      id: "kafka",
      name: "Apache Kafka Message Broker",
      type: "Event Streaming Cluster",
      endpoint: "Topic routex:traffic",
      status: "unverified",
      details: "No direct HTTP health probe. Background streaming worker handles Kafka; cannot be marked healthy based on frontend connectivity alone.",
      verifiedDirectly: false,
      lastSuccess: null,
      error: null,
    },
    {
      id: "yolo",
      name: "YOLO Computer Vision Worker",
      type: "Object Tracking Pipeline",
      endpoint: "Video Inference Pipeline",
      status: "unverified",
      details: "Computer vision processing pipeline runs as an asynchronous background worker without a direct REST health endpoint.",
      verifiedDirectly: false,
      lastSuccess: null,
      error: null,
    },
  ];

  const anyFailures = probes.filter((p) => p.status === "unhealthy");

  return (
    <div className="space-y-6">
      <PageHeader
        title="System Status & Service Diagnostics"
        subtitle="Verification of backend microservices, database connectivity, and data freshness"
        actions={
          <button
            type="button"
            onClick={handleRefreshAll}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors"
          >
            <RotateCw className="w-3.5 h-3.5" />
            <span>Re-probe All Components</span>
          </button>
        }
      />

      {/* Strict Verification Protocol Warning Notice */}
      <div className="rounded-xl border border-blue-500/30 bg-blue-950/20 p-4 text-xs text-blue-200 flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="font-semibold text-blue-100">Verified Health Reporting Protocol</p>
          <p className="text-blue-300/90 leading-relaxed">
            RouteX strictly verifies components through authentic HTTP/PostGIS/Redis endpoint probes.
            Components without direct HTTP probes (such as the Apache Kafka broker and background YOLO workers)
            are strictly marked as <strong className="text-white">Unverified</strong> rather than falsely reported as healthy.
          </p>
        </div>
      </div>

      {/* Grid of Component Probes */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {probes.map((probe) => {
          const isHealthy = probe.status === "healthy";
          const isChecking = probe.status === "checking";
          const isUnverified = probe.status === "unverified";

          return (
            <div
              key={probe.id}
              className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm flex flex-col justify-between shadow-lg"
            >
              <div>
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                      {probe.type}
                    </span>
                    <h3 className="text-sm font-bold text-white mt-0.5">{probe.name}</h3>
                  </div>

                  {isChecking ? (
                    <span className="w-2.5 h-2.5 rounded-full bg-slate-400 animate-pulse" />
                  ) : isHealthy ? (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <CheckCircle2 className="w-3 h-3" />
                      Verified Active
                    </span>
                  ) : isUnverified ? (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700">
                      <HelpCircle className="w-3 h-3" />
                      Unverified
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                      <ShieldAlert className="w-3 h-3" />
                      Failed
                    </span>
                  )}
                </div>

                <div className="mt-4 p-3 rounded-lg bg-slate-950/60 border border-slate-800/80 space-y-1.5 text-xs">
                  <div className="flex justify-between text-slate-400 text-[11px]">
                    <span>Probe Route:</span>
                    <span className="font-mono text-slate-300">{probe.endpoint}</span>
                  </div>

                  {probe.latencyMs !== undefined && (
                    <div className="flex justify-between text-slate-400 text-[11px]">
                      <span>Probe Latency:</span>
                      <span className="font-mono text-emerald-400">{probe.latencyMs} ms</span>
                    </div>
                  )}

                  <div className="text-[11px] text-slate-300 pt-1 border-t border-slate-800/60">
                    {probe.details}
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-800/80 text-[10px] text-slate-400 flex justify-between items-center">
                <span>Direct Probe: {probe.verifiedDirectly ? "Yes (HTTP)" : "No HTTP Endpoint"}</span>
                <span>Port 8001</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Freshness & Data Sync Ledger */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
          <Clock className="w-4 h-4 text-blue-400" />
          <h3 className="text-sm font-semibold text-white">Data Freshness & Refresh Timestamps</h3>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
          <div className="p-3.5 rounded-lg bg-slate-800/40 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
              <Server className="w-3.5 h-3.5 text-blue-400" />
              <span>FastAPI /health</span>
            </div>
            <span className="font-mono font-medium text-white block">
              {fastApiUpdatedAt ? formatTimestamp(new Date(fastApiUpdatedAt).toISOString()) : "Connecting..."}
            </span>
            <span className="text-[10px] text-emerald-400 mt-1 block">10s poll cadence</span>
          </div>

          <div className="p-3.5 rounded-lg bg-slate-800/40 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
              <Database className="w-3.5 h-3.5 text-emerald-400" />
              <span>PostgreSQL /roads/</span>
            </div>
            <span className="font-mono font-medium text-white block">
              {postgresUpdatedAt ? formatTimestamp(new Date(postgresUpdatedAt).toISOString()) : "Connecting..."}
            </span>
            <span className="text-[10px] text-emerald-400 mt-1 block">10s poll cadence</span>
          </div>

          <div className="p-3.5 rounded-lg bg-slate-800/40 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
              <Layers className="w-3.5 h-3.5 text-amber-400" />
              <span>Redis /live-traffic/</span>
            </div>
            <span className="font-mono font-medium text-white block">
              {redisUpdatedAt ? formatTimestamp(new Date(redisUpdatedAt).toISOString()) : "Connecting..."}
            </span>
            <span className="text-[10px] text-emerald-400 mt-1 block">10s poll cadence</span>
          </div>

          <div className="p-3.5 rounded-lg bg-slate-800/40 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
              <Cpu className="w-3.5 h-3.5 text-purple-400" />
              <span>ML /prediction/models</span>
            </div>
            <span className="font-mono font-medium text-white block">
              {mlUpdatedAt ? formatTimestamp(new Date(mlUpdatedAt).toISOString()) : "Connecting..."}
            </span>
            <span className="text-[10px] text-emerald-400 mt-1 block">10s poll cadence</span>
          </div>
        </div>
      </div>

      {/* Relevant API Failures & Diagnostic Log */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-semibold text-white">API Diagnostic & Failure Ledger</h3>
          </div>
          <span className="text-[11px] text-slate-400">
            {anyFailures.length === 0 ? "All verified endpoints healthy" : `${anyFailures.length} issue(s) detected`}
          </span>
        </div>

        {anyFailures.length === 0 ? (
          <div className="p-3.5 rounded-lg bg-emerald-950/20 border border-emerald-900/40 text-xs text-emerald-300 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>No active API connection failures. All probed REST endpoints responded with HTTP 200.</span>
          </div>
        ) : (
          <div className="space-y-2">
            {anyFailures.map((failure) => (
              <div
                key={failure.id}
                className="p-3 rounded-lg bg-rose-950/30 border border-rose-900/50 text-xs text-rose-200 space-y-1"
              >
                <div className="flex items-center justify-between font-bold">
                  <span>{failure.name} ({failure.endpoint})</span>
                  <span className="text-[10px] uppercase bg-rose-500/20 px-1.5 py-0.5 rounded text-rose-400">
                    Failed
                  </span>
                </div>
                <p className="text-[11px] text-rose-300/80">{failure.details}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
