import { apiClient } from "./client";

export interface BackendHealthResponse {
  status: string;
}

export interface IntegrationProbe {
  status: "healthy" | "unhealthy" | "reachable" | "unverified" | "unconfigured" | string;
  details: string;
  latency_ms: number | null;
  checked_at: string | null;
  error: string | null;
}

export interface IntegrationHealthResponse {
  checked_at: string;
  components: Record<string, IntegrationProbe>;
}

export async function getIntegrationHealth(signal?: AbortSignal): Promise<IntegrationHealthResponse> {
  const response = await apiClient.get<IntegrationHealthResponse>("/health/integrations", {
    signal,
    timeout: 5000,
  });
  return response.data;
}

export async function checkBackendConnection(): Promise<boolean> {
  try {
    const response = await apiClient.get<BackendHealthResponse>("/health");
    return response.status === 200 && response.data?.status === "healthy";
  } catch {
    return false;
  }
}

export async function getBackendHealth(): Promise<{ healthy: boolean; status: string; timestamp: string }> {
  try {
    const response = await apiClient.get<BackendHealthResponse>("/health");
    return {
      healthy: response.status === 200,
      status: response.data?.status || "reachable",
      timestamp: new Date().toISOString(),
    };
  } catch {
    return {
      healthy: false,
      status: "unreachable",
      timestamp: new Date().toISOString(),
    };
  }
}

