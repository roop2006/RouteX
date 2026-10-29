import { apiClient } from "./client";
import type { RoadSegment } from "../types/geography";

export async function getRoads(): Promise<RoadSegment[]> {
  const response = await apiClient.get<RoadSegment[]>("/roads/");
  return response.data;
}
