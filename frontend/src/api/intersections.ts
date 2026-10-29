import { apiClient } from "./client";
import type { Intersection } from "../types/geography";

export async function getIntersections(): Promise<Intersection[]> {
  const response = await apiClient.get<Intersection[]>("/intersections/");
  return response.data;
}
