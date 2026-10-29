import { apiClient } from "./client";
import type {
  CombinedAnalysisRequest,
  CombinedAnalysisResponse,
  LocationSuggestion,
  RouteAnalysisRequest,
  RouteAnalysisResponse,
  VideoAnalysisJobResponse,
  VideoAnalysisStatusResponse,
} from "../types/userAnalysis";

export async function analyzeRoute(request: RouteAnalysisRequest): Promise<RouteAnalysisResponse> {
  const response = await apiClient.post<RouteAnalysisResponse>("/analysis/route", request);
  return response.data;
}

export async function uploadVideoForAnalysis(
  file: File,
  intersectionId?: string
): Promise<VideoAnalysisJobResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (intersectionId) {
    formData.append("intersection_id", intersectionId);
  }

  const response = await apiClient.post<VideoAnalysisJobResponse>(
    "/analysis/video/upload",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      timeout: 120000, // 2 minutes for upload
    }
  );
  return response.data;
}

export async function startSampleVideoAnalysis(
  videoPath = "data/videos/traffic.mp4",
  intersectionId = "INT_001"
): Promise<VideoAnalysisJobResponse> {
  const response = await apiClient.post<VideoAnalysisJobResponse>("/analysis/video/sample", {
    video_path: videoPath,
    intersection_id: intersectionId,
  });
  return response.data;
}

export async function getVideoAnalysisStatus(
  jobId: string
): Promise<VideoAnalysisStatusResponse> {
  const response = await apiClient.get<VideoAnalysisStatusResponse>(
    `/analysis/video/${encodeURIComponent(jobId)}`
  );
  return response.data;
}

export async function cancelVideoAnalysis(jobId: string): Promise<{ message: string }> {
  const response = await apiClient.post<{ message: string }>(
    `/analysis/video/${encodeURIComponent(jobId)}/cancel`
  );
  return response.data;
}

export async function searchLocationSuggestions(
  query: string
): Promise<LocationSuggestion[]> {
  const response = await apiClient.get<LocationSuggestion[]>(
    `/analysis/geocoding/search`,
    {
      params: { q: query },
    }
  );
  return response.data;
}

export async function combineRouteAndVideo(
  request: CombinedAnalysisRequest
): Promise<CombinedAnalysisResponse> {
  const response = await apiClient.post<CombinedAnalysisResponse>(
    "/analysis/combine",
    request
  );
  return response.data;
}
