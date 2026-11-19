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
import { getRoads } from "../../api/roads";
import { getModelRegistry } from "../../api/predictions";
import { getIntegrationHealth } from "../../api/health";
import { formatTimestamp } from "../../utils/formatters";

interface ComponentProbe {
  id: string;
  name: string;
  type: string;
  endpoint: string;
  status: "healthy" | "unavailable" | "unverified" | "checking" | "degraded" | "not_configured" | "idle";
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
    refetchInterval: 30000,
  });

  // Probe Redis, Kafka TCP reachability, provider last results, and alert storage without triggering provider calls.
  const {
    data: integrationData,
    isLoading: isCheckingIntegrations,
    error: integrationError,
    refetch: refetchIntegrations,
    dataUpdatedAt: integrationsUpdatedAt,
  } = useQuery({
    queryKey: ["probe-integrations"],
    queryFn: ({ signal }) => getIntegrationHealth(signal),
    refetchInterval: 30000,
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
    refetchInterval: 30000,
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
    refetchInterval: 30000,
    retry: false,
  });

  const handleRefreshAll = () => {
    refetchFastApi();
    refetchIntegrations();
    refetchPostgres();
    refetchML();
  };

  const probeComponent = (key: string) => integrationData?.components[key];
  const probeStatus = (key: string): ComponentProbe["status"] => {
    if (isCheckingIntegrations) return "checking";
    const status = probeComponent(key)?.status;
    if (status === "healthy" || status === "available") return "healthy";
    if (status === "not_configured" || status === "unconfigured") return "not_configured";
    if (status === "idle" || status === "degraded") return status;
    if (status === "reachable") return "degraded";
    if (status === "unverified" || !status) return "unverified";
    return "unavailable";
  };

  const probes: ComponentProbe[] = [
    {
      id: "fastapi",
      name: "FastAPI Application Server",
      type: "Core REST Gateway",
      endpoint: "GET /health",
      status: isCheckingFastApi ? "checking" : fastApiHealth?.healthy ? "healthy" : "unavailable",
      latencyMs: fastApiHealth?.latency,
      details: fastApiHealth?.healthy
        ? "FastAPI responding at the configured endpoint"
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
      status: isCheckingPostgres ? "checking" : !postgresError && postgresData ? "healthy" : "unavailable",
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
      endpoint: "GET /health/integrations (PING)",
      status: integrationError ? "unavailable" : probeStatus("redis"),
      latencyMs: probeComponent("redis")?.latency_ms ?? undefined,
      details: probeComponent("redis")?.error || probeComponent("redis")?.details || integrationError?.message || "Redis status is not available",
      verifiedDirectly: true,
      lastSuccess: integrationsUpdatedAt ? new Date(integrationsUpdatedAt).toISOString() : null,
      error: probeComponent("redis")?.error || integrationError?.message || null,
    },
    {
      id: "ml",
      name: "AI Prediction Service",
      type: "RandomForest ML Pipeline",
      endpoint: "GET /prediction/models",
      status: isCheckingML ? "checking" : !mlError && mlData ? "healthy" : "unavailable",
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
      endpoint: "Configured Kafka broker",
      status: integrationError ? "unavailable" : probeStatus("kafka"),
      latencyMs: probeComponent("kafka")?.latency_ms ?? undefined,
      details: probeComponent("kafka")?.error || probeComponent("kafka")?.details || "Kafka status is not available",
      verifiedDirectly: true,
      lastSuccess: probeComponent("kafka")?.checked_at || null,
      error: probeComponent("kafka")?.error || integrationError?.message || null,
    },
    {
      id: "tomtom-flow",
      name: "TomTom Traffic Flow API",
      type: "External Live Provider",
      endpoint: "Traffic Services v4 Flow Segment",
      status: integrationError ? "unavailable" : probeStatus("tomtom_flow"),
      latencyMs: probeComponent("tomtom_flow")?.latency_ms ?? undefined,
      details: probeComponent("tomtom_flow")?.error || probeComponent("tomtom_flow")?.details || "Provider status is not available",
      verifiedDirectly: probeComponent("tomtom_flow")?.status === "available",
      lastSuccess: probeComponent("tomtom_flow")?.checked_at || null,
      error: probeComponent("tomtom_flow")?.error || integrationError?.message || null,
    },
    {
      id: "tomtom-incidents",
      name: "TomTom Traffic Incidents API",
      type: "External Live Provider",
      endpoint: "Traffic Services v5 Incident Details",
      status: integrationError ? "unavailable" : probeStatus("tomtom_incidents"),
      latencyMs: probeComponent("tomtom_incidents")?.latency_ms ?? undefined,
      details: probeComponent("tomtom_incidents")?.error || probeComponent("tomtom_incidents")?.details || "Provider status is not available",
      verifiedDirectly: probeComponent("tomtom_incidents")?.status === "available",
      lastSuccess: probeComponent("tomtom_incidents")?.checked_at || null,
      error: probeComponent("tomtom_incidents")?.error || integrationError?.message || null,
    },
    {
      id: "osrm",
      name: "OSRM Primary Routing",
      type: "External Routing Provider",
      endpoint: "router.project-osrm.org route service",
      status: integrationError ? "unavailable" : probeStatus("osrm"),
      latencyMs: probeComponent("osrm")?.latency_ms ?? undefined,
      details: probeComponent("osrm")?.error || probeComponent("osrm")?.details || "OSRM has not been probed yet",
      verifiedDirectly: probeComponent("osrm")?.status === "available",
      lastSuccess: probeComponent("osrm")?.checked_at || null,
      error: probeComponent("osrm")?.error || integrationError?.message || null,
    },
    {
      id: "alert-store",
      name: "Alert Rules & Persistence",
      type: "PostgreSQL Alert Engine",
      endpoint: "GET /health/integrations (alert tables)",
      status: integrationError ? "unavailable" : probeStatus("alert_store"),
      latencyMs: probeComponent("alert_store")?.latency_ms ?? undefined,
      details: probeComponent("alert_store")?.error || probeComponent("alert_store")?.details || "Alert store status is not available",
      verifiedDirectly: true,
      lastSuccess: integrationsUpdatedAt ? new Date(integrationsUpdatedAt).toISOString() : null,
      error: probeComponent("alert_store")?.error || integrationError?.message || null,
    },
    {
      id: "yolo",
      name: "YOLO Computer Vision Worker",
      type: "Object Tracking Pipeline",
      endpoint: "Video Inference Pipeline",
      status: integrationError ? "unavailable" : probeStatus("yolo"),
      details: probeComponent("yolo")?.details || "Video worker status unavailable",
      verifiedDirectly: true,
      lastSuccess: null,
      error: null,
    },
  ];

  const anyFailures = probes.filter((p) => p.status === "unavailable");

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
            Kafka is checked for broker TCP reachability; provider connectivity reflects the last real traffic request, and health refresh does not spend TomTom quota. YOLO reports the uploaded-video worker job state; idle means awaiting input. TCP reachability alone does not verify Kafka consumption.
          </p>
        </div>
      </div>

      {/* Grid of Component Probes */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {probes.map((probe) => {
          const isHealthy = probe.status === "healthy";
          const isChecking = probe.status === "checking";
          const isUnverified = ["unverified", "idle", "degraded", "not_configured"].includes(probe.status);

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
                      {probe.status === "not_configured" ? "Not configured" : probe.status === "idle" ? "Idle / awaiting input" : probe.status === "degraded" ? "Degraded" : "Unverified"}
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                      <ShieldAlert className="w-3 h-3" />
                      Unavailable
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
                <span>Evidence: {probe.verifiedDirectly ? "Service probe / job state" : "Last provider observation"}</span>
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
            <span className="text-[10px] text-emerald-400 mt-1 block">30s poll cadence</span>
          </div>

          <div className="p-3.5 rounded-lg bg-slate-800/40 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
              <Database className="w-3.5 h-3.5 text-emerald-400" />
              <span>PostgreSQL /roads/</span>
            </div>
            <span className="font-mono font-medium text-white block">
              {postgresUpdatedAt ? formatTimestamp(new Date(postgresUpdatedAt).toISOString()) : "Connecting..."}
            </span>
            <span className="text-[10px] text-emerald-400 mt-1 block">30s poll cadence</span>
          </div>

          <div className="p-3.5 rounded-lg bg-slate-800/40 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
              <Layers className="w-3.5 h-3.5 text-amber-400" />
              <span>Redis PING /health/integrations</span>
            </div>
            <span className="font-mono font-medium text-white block">
              {integrationsUpdatedAt ? formatTimestamp(new Date(integrationsUpdatedAt).toISOString()) : "Connecting..."}
            </span>
            <span className="text-[10px] text-emerald-400 mt-1 block">30s poll cadence</span>
          </div>

          <div className="p-3.5 rounded-lg bg-slate-800/40 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
              <Cpu className="w-3.5 h-3.5 text-purple-400" />
              <span>ML /prediction/models</span>
            </div>
            <span className="font-mono font-medium text-white block">
              {mlUpdatedAt ? formatTimestamp(new Date(mlUpdatedAt).toISOString()) : "Connecting..."}
            </span>
            <span className="text-[10px] text-emerald-400 mt-1 block">30s poll cadence</span>
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
            {anyFailures.length === 0 ? "No failed probes; review idle and unverified components" : `${anyFailures.length} issue(s) detected`}
          </span>
        </div>

        {anyFailures.length === 0 ? (
          <div className="p-3.5 rounded-lg bg-emerald-950/20 border border-emerald-900/40 text-xs text-emerald-300 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>No failed dependency probes. Idle, unconfigured, and unverified components are listed above.</span>
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
