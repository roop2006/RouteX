import React, { useState } from "react";
import { MapContainer, TileLayer, GeoJSON, useMap } from "react-leaflet";
import type { GeoJsonObject } from "geojson";
import type { NearbyTrafficEvent, Intersection, RoadSegment, TrafficZone } from "../../types/geography";
import { TrafficEventMarker, IntersectionMarker } from "./TrafficMarker";
import { Layers, Eye, EyeOff } from "lucide-react";

interface TrafficMapProps {
  events?: NearbyTrafficEvent[];
  intersections?: Intersection[];
  roads?: RoadSegment[];
  zones?: TrafficZone[];
  center?: [number, number];
  zoom?: number;
  selectedEventId?: number | null;
  onSelectEvent?: (event: NearbyTrafficEvent) => void;
  className?: string;
}

// Controller component to smoothly center on requested coordinates
const ChangeView: React.FC<{ center: [number, number]; zoom: number }> = ({ center, zoom }) => {
  const map = useMap();
  React.useEffect(() => {
    map.setView(center, zoom);
  }, [center, zoom, map]);
  return null;
};

export const TrafficMap: React.FC<TrafficMapProps> = ({
  events = [],
  intersections = [],
  roads = [],
  zones = [],
  center = [13.0827, 80.2707], // Default to RouteX urban intersection coordinates
  zoom = 14,
  onSelectEvent,
  className = "",
}) => {
  const [showEvents, setShowEvents] = useState(true);
  const [showIntersections, setShowIntersections] = useState(true);
  const [showRoads, setShowRoads] = useState(true);
  const [showZones, setShowZones] = useState(true);
  const [showTomTomFlow, setShowTomTomFlow] = useState(false);
  const [showTomTomIncidents, setShowTomTomIncidents] = useState(false);

  // Parse road geometries safely
  const parsedRoads = roads
    .filter((road) => road.geometry)
    .map((road) => {
      try {
        const geojson = JSON.parse(road.geometry as string) as GeoJsonObject;
        return { ...road, parsedGeoJson: geojson };
      } catch {
        return null;
      }
    })
    .filter(Boolean) as Array<RoadSegment & { parsedGeoJson: GeoJsonObject }>;

  // Parse zone geometries safely
  const parsedZones = zones
    .filter((zone) => zone.geometry)
    .map((zone) => {
      try {
        const geojson = JSON.parse(zone.geometry as string) as GeoJsonObject;
        return { ...zone, parsedGeoJson: geojson };
      } catch {
        return null;
      }
    })
    .filter(Boolean) as Array<TrafficZone & { parsedGeoJson: GeoJsonObject }>;

  return (
    <div className={`relative w-full h-full min-h-[450px] rounded-xl overflow-hidden border border-slate-800 bg-slate-950 ${className}`}>
      {/* Map Layer Controls floating panel */}
      <div className="absolute top-4 right-4 z-[1000] bg-slate-900/90 backdrop-blur-md border border-slate-800 rounded-lg p-2.5 shadow-xl text-xs space-y-2">
        <div className="flex items-center gap-1.5 font-semibold text-slate-300 border-b border-slate-800 pb-1.5">
          <Layers className="w-3.5 h-3.5 text-blue-400" />
          <span>Map Layers</span>
        </div>

        <div className="space-y-1">
          <button
            type="button"
            onClick={() => setShowEvents((prev) => !prev)}
            className={`w-full flex items-center justify-between gap-3 px-2 py-1 rounded text-left transition-colors ${
              showEvents ? "text-emerald-400 bg-emerald-950/30 font-medium" : "text-slate-400 hover:text-slate-300"
            }`}
          >
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              Events ({events.length})
            </span>
            {showEvents ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
          </button>

          <button
            type="button"
            onClick={() => setShowIntersections((prev) => !prev)}
            className={`w-full flex items-center justify-between gap-3 px-2 py-1 rounded text-left transition-colors ${
              showIntersections ? "text-indigo-400 bg-indigo-950/30 font-medium" : "text-slate-400 hover:text-slate-300"
            }`}
          >
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-sm bg-indigo-500"></span>
              Intersections ({intersections.length})
            </span>
            {showIntersections ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
          </button>

          <button
            type="button"
            onClick={() => setShowRoads((prev) => !prev)}
            className={`w-full flex items-center justify-between gap-3 px-2 py-1 rounded text-left transition-colors ${
              showRoads ? "text-blue-400 bg-blue-950/30 font-medium" : "text-slate-400 hover:text-slate-300"
            }`}
          >
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-0.5 bg-blue-400"></span>
              Roads ({parsedRoads.length})
            </span>
            {showRoads ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
          </button>

          <button
            type="button"
            onClick={() => setShowZones((prev) => !prev)}
            className={`w-full flex items-center justify-between gap-3 px-2 py-1 rounded text-left transition-colors ${
              showZones ? "text-purple-400 bg-purple-950/30 font-medium" : "text-slate-400 hover:text-slate-300"
            }`}
          >
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded bg-purple-500/50 border border-purple-400"></span>
              Zones ({parsedZones.length})
            </span>
            {showZones ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
          </button>

          <button
            type="button"
            onClick={() => setShowTomTomFlow((prev) => !prev)}
            className={`w-full flex items-center justify-between gap-3 px-2 py-1 rounded text-left transition-colors ${
              showTomTomFlow ? "text-emerald-400 bg-emerald-950/30 font-medium" : "text-slate-400 hover:text-slate-300"
            }`}
          >
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-0.5 bg-emerald-400"></span>
              TomTom Flow
            </span>
            {showTomTomFlow ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
          </button>

          <button
            type="button"
            onClick={() => setShowTomTomIncidents((prev) => !prev)}
            className={`w-full flex items-center justify-between gap-3 px-2 py-1 rounded text-left transition-colors ${
              showTomTomIncidents ? "text-rose-400 bg-rose-950/30 font-medium" : "text-slate-400 hover:text-slate-300"
            }`}
          >
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-rose-500"></span>
              TomTom Incidents
            </span>
            {showTomTomIncidents ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
          </button>
        </div>
      </div>

      {/* Legend pill */}
      <div className="absolute bottom-4 left-4 z-[1000] bg-slate-900/90 backdrop-blur-md border border-slate-800 rounded-lg px-3 py-1.5 shadow-xl text-[11px] flex items-center gap-3 text-slate-300">
        <span className="font-semibold text-slate-400">Congestion:</span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Low
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-amber-500"></span> Med
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-rose-500"></span> High
        </span>
      </div>

      <MapContainer
        center={center}
        zoom={zoom}
        scrollWheelZoom={true}
        className="w-full h-full z-10"
      >
        <ChangeView center={center} zoom={zoom} />

        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />

        {/* TomTom Live Flow Overlay Layer */}
        {showTomTomFlow && (
          <TileLayer
            attribution='&copy; <a href="https://www.tomtom.com">TomTom</a>'
            url={`${(import.meta.env.VITE_API_BASE_URL || "http://localhost:8001").replace(/\/+$/, "")}/live-traffic/tile/flow/{z}/{x}/{y}.png`}
            opacity={0.65}
            zIndex={15}
            maxZoom={19}
          />
        )}

        {/* TomTom Live Incidents Overlay Layer */}
        {showTomTomIncidents && (
          <TileLayer
            attribution='&copy; <a href="https://www.tomtom.com">TomTom</a>'
            url={`${(import.meta.env.VITE_API_BASE_URL || "http://localhost:8001").replace(/\/+$/, "")}/live-traffic/tile/incidents/{z}/{x}/{y}.png`}
            opacity={0.8}
            zIndex={16}
            maxZoom={19}
          />
        )}

        {/* Zones Layer (PostGIS Polygons) */}
        {showZones &&
          parsedZones.map((zone) => (
            <GeoJSON
              key={`zone-${zone.zone_id}`}
              data={zone.parsedGeoJson}
              style={{
                color: "#a855f7",
                weight: 2,
                fillColor: "#a855f7",
                fillOpacity: 0.15,
                dashArray: "4 4",
              }}
            />
          ))}

        {/* Roads Layer (PostGIS LineStrings) */}
        {showRoads &&
          parsedRoads.map((road) => (
            <GeoJSON
              key={`road-${road.road_id}`}
              data={road.parsedGeoJson}
              style={{
                color: "#38bdf8",
                weight: 4,
                opacity: 0.8,
              }}
            />
          ))}

        {/* Intersections Layer */}
        {showIntersections &&
          intersections.map((intersection) => (
            <IntersectionMarker
              key={`int-${intersection.intersection_id}`}
              intersection={intersection}
            />
          ))}

        {/* Traffic Events Layer */}
        {showEvents &&
          events.map((event) => (
            <TrafficEventMarker
              key={`event-${event.id}`}
              event={event}
              onSelect={onSelectEvent}
            />
          ))}
      </MapContainer>
    </div>
  );
};
