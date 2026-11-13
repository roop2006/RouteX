import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Network, Search, MapPin, Navigation, ArrowUpRight, LayoutGrid, Table } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { LoadingState } from "../../components/common/LoadingState";
import { ErrorState } from "../../components/common/ErrorState";
import { EmptyState } from "../../components/common/EmptyState";
import { useIntersections } from "../../hooks/useGeography";
import { useSelectedRoute } from "../../contexts/selectedRouteContext";
import type { CorridorIntersectionMatch } from "../../types/userAnalysis";

export const IntersectionsPage: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState("");
  const [viewMode, setViewMode] = useState<"cards" | "table">("cards");
  const routeContext = useSelectedRoute();
  const routeMode = Boolean(routeContext.analysis && routeContext.selectedRoute);
  const routeIntersections = routeContext.selectedRoute?.corridor?.nearby_intersections || [];
  const { data: registeredIntersections = [], isLoading: isLoadingRegistered, error: registeredError, refetch } = useIntersections(!routeMode);
  const intersections = routeMode ? routeIntersections : registeredIntersections;
  const isLoading = !routeMode && isLoadingRegistered;
  const error = !routeMode ? registeredError : null;

  const filtered = intersections.filter(
    (int) =>
      int.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      int.intersection_id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Intersections & Sensor Nodes"
        subtitle={routeMode ? "Registered intersections associated with the selected route corridor" : "Critical junction points, camera telemetry mounts, and PostGIS location fixtures"}
        badge={
          <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            {routeMode ? `${intersections.length} Route Matches` : `${intersections.length} Active Junctions`}
          </span>
        }
        actions={
          <div className="flex items-center gap-3">
            <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-1 text-xs">
              <button
                type="button"
                onClick={() => setViewMode("cards")}
                className={`p-1.5 rounded transition-colors ${
                  viewMode === "cards" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-slate-200"
                }`}
                title="Card View"
              >
                <LayoutGrid className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={() => setViewMode("table")}
                className={`p-1.5 rounded transition-colors ${
                  viewMode === "table" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-slate-200"
                }`}
                title="Table View"
              >
                <Table className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search junctions..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 w-52"
              />
            </div>
          </div>
        }
      />

      {routeMode && routeContext.selectedRoute && (
        <div className="rounded-lg border border-indigo-500/30 bg-indigo-950/20 p-3 text-xs text-slate-300">
          Intersections within the configured route corridor for {routeContext.origin?.name || "origin"} â†’ {routeContext.destination?.name || "destination"}.
          <span className="ml-2 text-slate-400">Only registered PostGIS nodes are shown.</span>
        </div>
      )}

      {isLoading ? (
        <LoadingState message="Loading intersection fixtures from database..." skeletonLines={3} />
      ) : error ? (
        <ErrorState
          title="Failed to Load Intersections"
          error={error}
          onRetry={() => refetch()}
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          title={routeMode ? "No Registered Intersections Along This Route" : "No Intersections Found"}
          description={searchTerm
            ? `No junction matches "${searchTerm}".`
            : routeMode
            ? "No registered intersection geometry falls within the configured route corridor."
            : "No intersections registered in database."}
        />
      ) : viewMode === "table" ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden backdrop-blur-sm shadow-xl">
          <div className="p-4 border-b border-slate-800 flex items-center justify-between">
            <span className="text-sm font-semibold text-white">Intersection Inventory Table</span>
            <span className="text-xs text-slate-400 font-mono">Showing {filtered.length} nodes</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-medium uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3 px-4">Node ID</th>
                  <th className="py-3 px-4">Intersection Name</th>
                  <th className="py-3 px-4">Latitude</th>
                  <th className="py-3 px-4">Longitude</th>
                  {routeMode && <th className="py-3 px-4">Route Offset / Roads</th>}
                  {routeMode && <th className="py-3 px-4">Traffic Observation</th>}
                  <th className="py-3 px-4">Coordinate System</th>
                  <th className="py-3 px-4 text-right">Map Link</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filtered.map((item) => (
                  <tr key={item.intersection_id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-indigo-400">{item.intersection_id}</td>
                    <td className="py-3 px-4 font-bold text-white">{item.name}</td>
                    <td className="py-3 px-4 font-mono text-slate-200">{item.latitude.toFixed(4)}</td>
                    <td className="py-3 px-4 font-mono text-slate-200">{item.longitude.toFixed(4)}</td>
                    {routeMode && <td className="py-3 px-4 text-slate-300">{Math.round((item as CorridorIntersectionMatch).distance_to_route_meters || 0)} m / {((item as CorridorIntersectionMatch).associated_road_ids || []).join(", ") || "No associated road"}</td>}
                    {routeMode && <td className="py-3 px-4 text-slate-300">{(item as CorridorIntersectionMatch).observed_average_speed == null ? "No observation" : `${(item as CorridorIntersectionMatch).observed_average_speed} km/h â€¢ ${(item as CorridorIntersectionMatch).observed_congestion || "Unknown"} â€¢ ${(item as CorridorIntersectionMatch).observation_count || 0} records`}</td>}
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-emerald-400 border border-slate-700">
                        SRID 4326 Point
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        to={`/map?lat=${item.latitude}&lng=${item.longitude}`}
                        className="inline-flex items-center gap-1 text-indigo-400 hover:text-indigo-300 font-medium"
                      >
                        <MapPin className="w-3.5 h-3.5" />
                        <span>Locate</span>
                        <ArrowUpRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filtered.map((item) => (
            <div
              key={item.intersection_id}
              className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm flex flex-col justify-between hover:border-slate-700/80 transition-all shadow-lg"
            >
              <div>
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-[11px] font-mono uppercase tracking-wider text-indigo-400 font-semibold">
                      {item.intersection_id}
                    </span>
                    <h3 className="text-base font-bold text-white mt-0.5">{item.name}</h3>
                  </div>
                  <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400">
                    <Network className="w-4 h-4" />
                  </div>
                </div>

                <div className="mt-4 p-3 rounded-lg bg-slate-800/40 border border-slate-800 space-y-2 text-xs">
                  <div className="flex justify-between items-center text-slate-300">
                    <span className="text-slate-400 flex items-center gap-1.5">
                      <MapPin className="w-3.5 h-3.5 text-slate-400" /> Latitude
                    </span>
                    <span className="font-mono text-white font-medium">
                      {item.latitude.toFixed(4)}
                    </span>
                  </div>

                  <div className="flex justify-between items-center text-slate-300">
                    <span className="text-slate-400 flex items-center gap-1.5">
                      <Navigation className="w-3.5 h-3.5 text-slate-400" /> Longitude
                    </span>
                    <span className="font-mono text-white font-medium">
                      {item.longitude.toFixed(4)}
                    </span>
                  </div>

                  <div className="flex justify-between items-center text-slate-300 pt-1 border-t border-slate-800/80">
                    <span className="text-slate-400">PostGIS Geometry</span>
                    <span className="font-mono text-emerald-400 text-[11px]">SRID 4326 Point</span>
                  </div>
                  {routeMode && (
                    <>
                      <div className="flex justify-between items-center text-slate-300">
                        <span className="text-slate-400">Distance from route</span>
                        <span className="font-mono text-white">{Math.round((item as CorridorIntersectionMatch).distance_to_route_meters || 0)} m</span>
                      </div>
                      <div className="flex justify-between items-center text-slate-300">
                        <span className="text-slate-400">Associated roads</span>
                        <span className="font-mono text-white">{(item as CorridorIntersectionMatch).associated_road_ids?.join(", ") || "None registered nearby"}</span>
                      </div>
                      <div className="flex justify-between items-center text-slate-300">
                        <span className="text-slate-400">Traffic status</span>
                        <span className="font-mono text-white">{(item as CorridorIntersectionMatch).observed_congestion || "No observation"}</span>
                      </div>
                      {(item as CorridorIntersectionMatch).observed_average_speed != null && (
                        <div className="flex justify-between items-center text-slate-300">
                          <span className="text-slate-400">Observed speed / records</span>
                          <span className="font-mono text-white">{(item as CorridorIntersectionMatch).observed_average_speed} km/h / {(item as CorridorIntersectionMatch).observation_count || 0}</span>
                        </div>
                      )}
                      {(item as CorridorIntersectionMatch).last_observation_at && (
                        <div className="text-slate-400">Last observed: {(item as CorridorIntersectionMatch).last_observation_at}</div>
                      )}
                    </>
                  )}
                </div>
              </div>

              <div className="mt-5 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                <span className="text-[11px] text-slate-400">
                  Stationary Sensor Node
                </span>

                <Link
                  to={`/map?lat=${item.latitude}&lng=${item.longitude}`}
                  className="inline-flex items-center gap-1.5 text-indigo-400 hover:text-indigo-300 font-medium"
                >
                  <MapPin className="w-3.5 h-3.5" />
                  <span>Locate on Map</span>
                  <ArrowUpRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
