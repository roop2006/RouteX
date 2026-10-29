import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Activity,
  Info,
  Car,
  Gauge,
  RotateCw,
  X,
} from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { TrafficMap } from "../../components/map/TrafficMap";
import { ErrorState } from "../../components/common/ErrorState";
import { useRoads, useIntersections, useZones, useNearbyEvents } from "../../hooks/useGeography";
import type { NearbyTrafficEvent } from "../../types/geography";
import { formatSpeed, formatDensity, formatTimeOnly } from "../../utils/formatters";
import { getCongestionBadgeClass } from "../../utils/congestion";

export const MapPage: React.FC = () => {
  const [searchParams] = useSearchParams();

  // Derive map center & zoom from URL query params (or default RouteX junction)
  const paramLat = searchParams.get("lat") ? parseFloat(searchParams.get("lat")!) : null;
  const paramLng = searchParams.get("lng") ? parseFloat(searchParams.get("lng")!) : null;
  const hasQueryCoords = paramLat !== null && paramLng !== null && !isNaN(paramLat) && !isNaN(paramLng);

  const mapCenter: [number, number] = hasQueryCoords ? [paramLat, paramLng] : [13.0827, 80.2707];
  const mapZoom = hasQueryCoords ? 16 : 14;

  const [selectedEvent, setSelectedEvent] = useState<NearbyTrafficEvent | null>(null);

  // Query geospatial data from backend
  const { data: roads = [], error: roadsError } = useRoads();
  const { data: intersections = [], error: intError } = useIntersections();
  const { data: zones = [], error: zonesError } = useZones();
  const {
    data: nearbyEvents = [],
    error: eventsError,
    refetch: refetchEvents,
    isFetching: isFetchingEvents,
  } = useNearbyEvents({
    latitude: mapCenter[0],
    longitude: mapCenter[1],
    radius_meters: 10000,
  });

  const error = roadsError || intError || zonesError || eventsError;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Interactive Traffic Map"
        subtitle="Geospatial distribution of real-time stream events, intersections, road corridors, and congestion zones"
        actions={
          <button
            type="button"
            onClick={() => refetchEvents()}
            disabled={isFetchingEvents}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isFetchingEvents ? "animate-spin" : ""}`} />
            <span>Refresh Events</span>
          </button>
        }
      />

      {error && (
        <ErrorState
          title="Geospatial Data Loading Error"
          error={error}
          onRetry={() => refetchEvents()}
        />
      )}

      {/* Map and Detail Drawer Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-3 h-[620px] relative">
          <TrafficMap
            events={nearbyEvents}
            intersections={intersections}
            roads={roads}
            zones={zones}
            center={mapCenter}
            zoom={mapZoom}
            onSelectEvent={(evt) => setSelectedEvent(evt)}
            className="h-full"
          />
        </div>

        {/* Selected Item Detail Panel */}
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm">
            <h3 className="text-sm font-semibold text-white border-b border-slate-800 pb-3 flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Info className="w-4 h-4 text-blue-400" />
                <span>Geospatial Inspector</span>
              </span>
              {selectedEvent && (
                <button
                  type="button"
                  onClick={() => setSelectedEvent(null)}
                  className="text-slate-400 hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </h3>

            {selectedEvent ? (
              <div className="mt-4 space-y-3.5 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400 font-mono">Stream Event #{selectedEvent.id}</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${getCongestionBadgeClass(selectedEvent.congestion_level)}`}>
                    {selectedEvent.congestion_level}
                  </span>
                </div>

                <div className="p-3 rounded-lg bg-slate-800/40 border border-slate-800 space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400 flex items-center gap-1.5">
                      <Car className="w-3.5 h-3.5 text-blue-400" /> Total Vehicles
                    </span>
                    <span className="font-mono font-bold text-white text-sm">
                      {selectedEvent.total_vehicles}
                    </span>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-slate-400 flex items-center gap-1.5">
                      <Gauge className="w-3.5 h-3.5 text-emerald-400" /> Avg Speed
                    </span>
                    <span className="font-mono font-bold text-white">
                      {formatSpeed(selectedEvent.average_speed)}
                    </span>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-slate-400 flex items-center gap-1.5">
                      <Activity className="w-3.5 h-3.5 text-amber-400" /> Density
                    </span>
                    <span className="font-mono text-white">
                      {formatDensity(selectedEvent.density)}
                    </span>
                  </div>
                </div>

                <div className="space-y-1 text-slate-300">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Intersection</span>
                    <span className="font-mono">{selectedEvent.intersection_id || "Unassigned"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Coordinates</span>
                    <span className="font-mono text-[11px]">
                      {selectedEvent.latitude.toFixed(4)}, {selectedEvent.longitude.toFixed(4)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Timestamp</span>
                    <span className="font-mono text-[11px] text-slate-300">
                      {formatTimeOnly(selectedEvent.timestamp)}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-slate-400">
                Click on any traffic event pin or intersection marker on the map to inspect its real-time telemetry.
              </div>
            )}
          </div>

          {/* Quick Stats Summary */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 text-xs space-y-2.5">
            <h4 className="font-semibold text-slate-300 uppercase tracking-wider text-[11px]">
              Geospatial Inventory
            </h4>
            <div className="flex justify-between text-slate-400">
              <span>Nearby Traffic Events</span>
              <span className="font-mono font-bold text-white">{nearbyEvents.length}</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Road Segments</span>
              <span className="font-mono font-bold text-blue-400">{roads.length}</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Intersections</span>
              <span className="font-mono font-bold text-indigo-400">{intersections.length}</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Congestion Zones</span>
              <span className="font-mono font-bold text-purple-400">{zones.length}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
