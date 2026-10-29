import { apiClient } from "./client";

export interface BackendHealthResponse {
  status: string;
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

