import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  analyzeRoute,
  uploadVideoForAnalysis,
  startSampleVideoAnalysis,
  getVideoAnalysisStatus,
  cancelVideoAnalysis,
  searchLocationSuggestions,
  combineRouteAndVideo,
} from "../api/userAnalysis";
import type {
  RouteAnalysisRequest,
  CombinedAnalysisRequest,
} from "../types/userAnalysis";

export function useLocationSuggestions(query: string, enabled = true) {
  return useQuery({
    queryKey: ["location-suggestions", query],
    queryFn: () => searchLocationSuggestions(query),
    enabled: enabled && (query.trim().length >= 1 || query === ""),
    staleTime: 60000,
  });
}

export function useRouteAnalysis() {
  return useMutation({
    mutationFn: (request: RouteAnalysisRequest) => analyzeRoute(request),
  });
}

export function useVideoUpload() {
  return useMutation({
    mutationFn: ({ file, intersectionId }: { file: File; intersectionId?: string }) =>
      uploadVideoForAnalysis(file, intersectionId),
  });
}

export function useSampleVideoAnalysis() {
  return useMutation({
    mutationFn: ({ videoPath, intersectionId }: { videoPath?: string; intersectionId?: string }) =>
      startSampleVideoAnalysis(videoPath, intersectionId),
  });
}

export function useVideoAnalysisStatus(jobId: string | null) {
  return useQuery({
    queryKey: ["video-analysis-status", jobId],
    queryFn: () => (jobId ? getVideoAnalysisStatus(jobId) : null),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "COMPLETED" || status === "FAILED" || status === "CANCELLED") {
        return false;
      }
      return 1500; // Poll every 1.5 seconds while in progress
    },
  });
}

export function useCancelVideoAnalysis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => cancelVideoAnalysis(jobId),
    onSuccess: (_data, jobId) => {
      queryClient.invalidateQueries({ queryKey: ["video-analysis-status", jobId] });
    },
  });
}

export function useCombinedAnalysis() {
  return useMutation({
    mutationFn: (request: CombinedAnalysisRequest) => combineRouteAndVideo(request),
  });
}
