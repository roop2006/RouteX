import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Route, Search, MapPin, LayoutGrid, Table, ArrowUpRight } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { LoadingState } from "../../components/common/LoadingState";
import { ErrorState } from "../../components/common/ErrorState";
import { EmptyState } from "../../components/common/EmptyState";
import { useRoads } from "../../hooks/useGeography";

export const RoadsPage: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState("");
  const [viewMode, setViewMode] = useState<"cards" | "table">("cards");
  const { data: roads = [], isLoading, error, refetch } = useRoads();

  const filteredRoads = roads.filter(
    (road) =>
      road.road_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      road.road_id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Road Segments"
        subtitle="Monitored road infrastructure, speed limits, and geometric corridors"
        badge={
          <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
            {roads.length} Corridors
          </span>
        }
        actions={
          <div className="flex items-center gap-3">
            <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-1 text-xs">
              <button
                type="button"
                onClick={() => setViewMode("cards")}
                className={`p-1.5 rounded transition-colors ${
                  viewMode === "cards" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-slate-200"
                }`}
                title="Card View"
              >
                <LayoutGrid className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={() => setViewMode("table")}
                className={`p-1.5 rounded transition-colors ${
                  viewMode === "table" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-slate-200"
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
                placeholder="Search roads..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 w-52"
              />
            </div>
          </div>
        }
      />

      {isLoading ? (
        <LoadingState message="Loading road segments from PostGIS database..." skeletonLines={3} />
      ) : error ? (
        <ErrorState
          title="Failed to Load Roads"
          error={error}
          onRetry={() => refetch()}
        />
      ) : filteredRoads.length === 0 ? (
        <EmptyState
          title="No Road Segments Found"
          description={searchTerm ? `No road matches query "${searchTerm}".` : "No road segments configured in the database."}
        />
      ) : viewMode === "table" ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden backdrop-blur-sm shadow-xl">
          <div className="p-4 border-b border-slate-800 flex items-center justify-between">
            <span className="text-sm font-semibold text-white">Road Infrastructure Table</span>
            <span className="text-xs text-slate-400 font-mono">Showing {filteredRoads.length} segments</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-medium uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3 px-4">Road ID</th>
                  <th className="py-3 px-4">Road Name</th>
                  <th className="py-3 px-4">Speed Limit</th>
                  <th className="py-3 px-4">Lanes</th>
                  <th className="py-3 px-4">Geometry Type</th>
                  <th className="py-3 px-4 text-right">Map Link</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredRoads.map((road) => {
                  let firstCoord: [number, number] | null = null;
                  if (road.geometry) {
                    try {
                      const geo = JSON.parse(road.geometry);
                      if (geo.coordinates && geo.coordinates.length > 0) {
                        const [lng, lat] = geo.coordinates[0];
                        firstCoord = [lat, lng];
                      }
                    } catch {
                      firstCoord = null;
                    }
                  }

                  return (
                    <tr key={road.road_id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 px-4 font-mono font-bold text-blue-400">{road.road_id}</td>
                      <td className="py-3 px-4 font-bold text-white">{road.road_name}</td>
                      <td className="py-3 px-4 font-mono text-slate-200">{road.speed_limit} km/h</td>
                      <td className="py-3 px-4 font-mono text-slate-200">{road.lanes} {road.lanes === 1 ? "lane" : "lanes"}</td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300 border border-slate-700">
                          {road.geometry ? "LineString (GeoJSON)" : "No Geometry"}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        {firstCoord ? (
                          <Link
                            to={`/map?lat=${firstCoord[0]}&lng=${firstCoord[1]}`}
                            className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 font-medium"
                          >
                            <MapPin className="w-3.5 h-3.5" />
                            <span>Locate</span>
                            <ArrowUpRight className="w-3.5 h-3.5" />
                          </Link>
                        ) : (
                          <Link to="/map" className="text-slate-400 hover:text-slate-300">
                            Map
                          </Link>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredRoads.map((road) => {
            // Check if geometry contains coordinates we can navigate to
            let firstCoord: [number, number] | null = null;
            if (road.geometry) {
              try {
                const geo = JSON.parse(road.geometry);
                if (geo.coordinates && geo.coordinates.length > 0) {
                  // GeoJSON coords are [lng, lat]
                  const [lng, lat] = geo.coordinates[0];
                  firstCoord = [lat, lng];
                }
              } catch {
                firstCoord = null;
              }
            }

            return (
              <div
                key={road.road_id}
                className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm flex flex-col justify-between hover:border-slate-700/80 transition-all shadow-lg"
              >
                <div>
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-[11px] font-mono uppercase tracking-wider text-blue-400 font-semibold">
                        {road.road_id}
                      </span>
                      <h3 className="text-base font-bold text-white mt-0.5">{road.road_name}</h3>
                    </div>
                    <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
                      <Route className="w-4 h-4" />
                    </div>
                  </div>

                  <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                    <div className="p-2.5 rounded bg-slate-800/40 border border-slate-800">
                      <span className="text-slate-400 block text-[10px] uppercase">Speed Limit</span>
                      <span className="font-mono font-bold text-white text-sm">
                        {road.speed_limit} km/h
                      </span>
                    </div>

                    <div className="p-2.5 rounded bg-slate-800/40 border border-slate-800">
                      <span className="text-slate-400 block text-[10px] uppercase">Lanes</span>
                      <span className="font-mono font-bold text-white text-sm">
                        {road.lanes} {road.lanes === 1 ? "Lane" : "Lanes"}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="mt-5 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                  <span className="text-[11px] text-slate-400">
                    {road.geometry ? "LineString GeoJSON Available" : "No Shape Data"}
                  </span>

                  {firstCoord ? (
                    <Link
                      to={`/map?lat=${firstCoord[0]}&lng=${firstCoord[1]}`}
                      className="inline-flex items-center gap-1.5 text-blue-400 hover:text-blue-300 font-medium"
                    >
                      <MapPin className="w-3.5 h-3.5" />
                      <span>View on Map</span>
                    </Link>
                  ) : (
                    <Link
                      to="/map"
                      className="inline-flex items-center gap-1.5 text-slate-400 hover:text-slate-300"
                    >
                      <span>Map</span>
                    </Link>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
