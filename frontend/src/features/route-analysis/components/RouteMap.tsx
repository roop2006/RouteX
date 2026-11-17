import React, { useEffect } from "react";
import { MapContainer, TileLayer, GeoJSON, Marker, Popup, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import type { GeoJsonObject } from "geojson";
import type { RouteCoordinates, RouteAlternative } from "../../../types/userAnalysis";
import type { Intersection, RoadSegment, TrafficZone } from "../../../types/geography";
import { IntersectionMarker } from "../../../components/map/TrafficMarker";
import { MapPin, Navigation, Eye, EyeOff, Layers } from "lucide-react";
import { RouteAlertLayer } from "../../../components/map/RouteAlertLayer";

// Custom Origin Marker Icon (Green 'A')
function createOriginIcon(label = "A"): L.DivIcon {
  return L.divIcon({
    className: "custom-origin-pin",
    html: `
      <div style="position: relative; width: 34px; height: 34px; display: flex; align-items: center; justify-content: center;">
        <span style="position: absolute; width: 100%; height: 100%; border-radius: 50%; background: rgba(16, 185, 129, 0.45); animation: pulse 2s infinite;"></span>
        <div style="position: relative; width: 28px; height: 28px; border-radius: 50%; background: #10b981; border: 2.5px solid #ffffff; display: flex; align-items: center; justify-content: center; color: white; font-size: 13px; font-weight: 800; box-shadow: 0 4px 12px rgba(0,0,0,0.6);">
          ${label}
        </div>
      </div>
    `,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
    popupAnchor: [0, -17],
  });
}

// Custom Destination Marker Icon (Rose 'B')
function createDestinationIcon(label = "B"): L.DivIcon {
  return L.divIcon({
    className: "custom-dest-pin",
    html: `
      <div style="position: relative; width: 34px; height: 34px; display: flex; align-items: center; justify-content: center;">
        <span style="position: absolute; width: 100%; height: 100%; border-radius: 50%; background: rgba(244, 63, 94, 0.45); animation: pulse 2s infinite;"></span>
        <div style="position: relative; width: 28px; height: 28px; border-radius: 50%; background: #f43f5e; border: 2.5px solid #ffffff; display: flex; align-items: center; justify-content: center; color: white; font-size: 13px; font-weight: 800; box-shadow: 0 4px 12px rgba(0,0,0,0.6);">
          ${label}
        </div>
      </div>
    `,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
    popupAnchor: [0, -17],
  });
}

// Invalidate map size on initial mount/layout stabilization to prevent gray/unrendered tiles
const InvalidateSizeOnMount: React.FC = () => {
  const map = useMap();
  useEffect(() => {
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 250);
    return () => clearTimeout(timer);
  }, [map]);
  return null;
};

// Map bounds controller to auto-center when origin, destination or route change
const AutoBoundsController: React.FC<{
  origin?: RouteCoordinates | null;
  destination?: RouteCoordinates | null;
  routeGeometry?: RouteAlternative["geometry"] | null;
}> = ({ origin, destination, routeGeometry }) => {
  const map = useMap();

  useEffect(() => {
    if (routeGeometry?.coordinates && routeGeometry.coordinates.length > 0) {
      // routeGeometry coordinates are [lng, lat]
      const validCoords = routeGeometry.coordinates.filter(
        (c) => Array.isArray(c) && c.length >= 2 && Number.isFinite(c[0]) && Number.isFinite(c[1])
      );
      if (validCoords.length > 0) {
        const latlngs: [number, number][] = validCoords.map((c) => [c[1], c[0]]);
        const bounds = L.latLngBounds(latlngs);
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
      }
    } else if (
      origin &&
      destination &&
      Number.isFinite(origin.lat) &&
      Number.isFinite(origin.lng) &&
      Number.isFinite(destination.lat) &&
      Number.isFinite(destination.lng)
    ) {
      const bounds = L.latLngBounds([
        [origin.lat, origin.lng],
        [destination.lat, destination.lng],
      ]);
      map.fitBounds(bounds, { padding: [60, 60], maxZoom: 15 });
    } else if (origin && Number.isFinite(origin.lat) && Number.isFinite(origin.lng)) {
      map.setView([origin.lat, origin.lng], 14);
    } else if (destination && Number.isFinite(destination.lat) && Number.isFinite(destination.lng)) {
      map.setView([destination.lat, destination.lng], 14);
    }
  }, [origin, destination, routeGeometry, map]);

  return null;
};

// Map click listener for interactive map-based pin placement
const MapClickHandler: React.FC<{
  onMapClick?: (lat: number, lng: number) => void;
}> = ({ onMapClick }) => {
  useMapEvents({
    click(e) {
      if (onMapClick) {
        onMapClick(e.latlng.lat, e.latlng.lng);
      }
    },
  });
  return null;
};

interface RouteMapProps {
  origin?: RouteCoordinates | null;
  destination?: RouteCoordinates | null;
  selectedRoute?: RouteAlternative | null;
  alternatives?: RouteAlternative[];
  onSelectAlternative?: (alt: RouteAlternative) => void;
  intersections?: Intersection[];
  roads?: RoadSegment[];
  zones?: TrafficZone[];
  onMapClick?: (lat: number, lng: number, name?: string, forceTarget?: "origin" | "destination") => void;
  clickMode?: "origin" | "destination" | null;
  className?: string;
}

export const RouteMap: React.FC<RouteMapProps> = ({
  origin,
  destination,
  selectedRoute,
  alternatives = [],
  onSelectAlternative,
  intersections = [],
  roads = [],
  zones = [],
  onMapClick,
  clickMode = null,
  className = "",
}) => {
  const [showRoads, setShowRoads] = React.useState(true);
  const [showIntersections, setShowIntersections] = React.useState(true);
  const [showZones, setShowZones] = React.useState(true);
  const [showTomTomFlow, setShowTomTomFlow] = React.useState(false);
  const [showTomTomIncidents, setShowTomTomIncidents] = React.useState(false);

  const defaultCenter: [number, number] = [13.0827, 80.2707];

  // Parse road geometries safely
  const parsedRoads = roads
    .filter((r) => r.geometry)
    .map((r) => {
      try {
        const geojson = JSON.parse(r.geometry as string) as GeoJsonObject;
        return { ...r, parsedGeoJson: geojson };
      } catch {
        return null;
      }
    })
    .filter(Boolean) as Array<RoadSegment & { parsedGeoJson: GeoJsonObject }>;

  // Parse zone geometries safely
  const parsedZones = zones
    .filter((z) => z.geometry)
    .map((z) => {
      try {
        const geojson = JSON.parse(z.geometry as string) as GeoJsonObject;
        return { ...z, parsedGeoJson: geojson };
      } catch {
        return null;
      }
    })
    .filter(Boolean) as Array<TrafficZone & { parsedGeoJson: GeoJsonObject }>;

  // Color helper based on congestion level
  const getRouteColor = (congestion: string) => {
    switch (congestion.toUpperCase()) {
      case "HIGH":
        return "#ef4444";
      case "MEDIUM":
        return "#f59e0b";
      case "LOW":
        return "#10b981";
      default:
        return "#3b82f6";
    }
  };

  return (
    <div className={`relative w-full h-full min-h-[480px] rounded-xl overflow-hidden border border-slate-800 bg-slate-950 ${className}`}>
      {/* Click Mode Notification Banner */}
      {clickMode && (
        <div className="absolute top-4 left-4 z-[1000] bg-blue-600/90 text-white backdrop-blur-md px-3 py-1.5 rounded-lg shadow-xl text-xs font-semibold flex items-center gap-2 animate-bounce">
          <Navigation className="w-3.5 h-3.5" />
          <span>Click on the map to set {clickMode === "origin" ? "Origin (A)" : "Destination (B)"}</span>
        </div>
      )}

      {/* Map Layer Controls floating panel */}
      <div className="absolute top-4 right-4 z-[1000] bg-slate-900/90 backdrop-blur-md border border-slate-800 rounded-lg p-2.5 shadow-xl text-xs space-y-1.5">
        <div className="flex items-center gap-1.5 font-semibold text-slate-300 border-b border-slate-800 pb-1">
          <Layers className="w-3.5 h-3.5 text-blue-400" />
          <span>Layers</span>
        </div>

        <button
          type="button"
          onClick={() => setShowIntersections((prev) => !prev)}
          className={`w-full flex items-center justify-between gap-2 px-1.5 py-0.5 rounded text-left transition-colors ${
            showIntersections ? "text-indigo-400 font-medium" : "text-slate-400"
          }`}
        >
          <span>Intersections ({intersections.length})</span>
          {showIntersections ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
        </button>

        <button
          type="button"
          onClick={() => setShowRoads((prev) => !prev)}
          className={`w-full flex items-center justify-between gap-2 px-1.5 py-0.5 rounded text-left transition-colors ${
            showRoads ? "text-blue-400 font-medium" : "text-slate-400"
          }`}
        >
          <span>Roads ({parsedRoads.length})</span>
          {showRoads ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
        </button>

        <button
          type="button"
          onClick={() => setShowZones((prev) => !prev)}
          className={`w-full flex items-center justify-between gap-2 px-1.5 py-0.5 rounded text-left transition-colors ${
            showZones ? "text-purple-400 font-medium" : "text-slate-400"
          }`}
        >
          <span>Zones ({parsedZones.length})</span>
          {showZones ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
        </button>

        <button
          type="button"
          onClick={() => setShowTomTomFlow((prev) => !prev)}
          className={`w-full flex items-center justify-between gap-2 px-1.5 py-0.5 rounded text-left transition-colors ${
            showTomTomFlow ? "text-emerald-400 font-medium" : "text-slate-400"
          }`}
        >
          <span>TomTom Flow</span>
          {showTomTomFlow ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
        </button>

        <button
          type="button"
          onClick={() => setShowTomTomIncidents((prev) => !prev)}
          className={`w-full flex items-center justify-between gap-2 px-1.5 py-0.5 rounded text-left transition-colors ${
            showTomTomIncidents ? "text-rose-400 font-medium" : "text-slate-400"
          }`}
        >
          <span>TomTom Incidents</span>
          {showTomTomIncidents ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
        </button>
      </div>

      {/* Map Legend */}
      <div className="absolute bottom-4 left-4 z-[1000] bg-slate-900/90 backdrop-blur-md border border-slate-800 rounded-lg px-3 py-1.5 shadow-xl text-[11px] flex items-center gap-3 text-slate-300">
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 font-bold text-[9px] text-white flex items-center justify-center">A</span> Origin
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-rose-500 font-bold text-[9px] text-white flex items-center justify-center">B</span> Destination
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-1 bg-blue-500 rounded-full"></span> Route
        </span>
      </div>

      <MapContainer
        center={origin && Number.isFinite(origin.lat) && Number.isFinite(origin.lng) ? [origin.lat, origin.lng] : defaultCenter}
        zoom={14}
        scrollWheelZoom={true}
        className="w-full h-full z-10"
      >
        <InvalidateSizeOnMount />
        <AutoBoundsController
          origin={origin}
          destination={destination}
          routeGeometry={selectedRoute?.geometry}
        />
        <MapClickHandler onMapClick={onMapClick} />

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

        {/* Traffic Zones Layer */}
        {showZones &&
          parsedZones.map((zone) => (
            <GeoJSON
              key={`zone-${zone.zone_id}`}
              data={zone.parsedGeoJson}
              style={{
                color: "#a855f7",
                weight: 2,
                fillColor: "#a855f7",
                fillOpacity: 0.12,
                dashArray: "4 4",
              }}
            />
          ))}

        {/* Road Segments Layer */}
        {showRoads &&
          parsedRoads.map((road) => (
            <GeoJSON
              key={`road-${road.road_id}`}
              data={road.parsedGeoJson}
              style={{
                color: "#475569",
                weight: 3,
                opacity: 0.6,
              }}
            />
          ))}

        {/* Alternative Routes (Dashed, background) */}
        {alternatives.map((alt, idx) => {
          if (selectedRoute && alt.summary === selectedRoute.summary) return null;
          return (
            <GeoJSON
              key={`alt-route-${idx}`}
              data={alt.geometry as unknown as GeoJsonObject}
              style={{
                color: "#64748b",
                weight: 4,
                opacity: 0.6,
                dashArray: "6 6",
              }}
              eventHandlers={{
                click: () => onSelectAlternative?.(alt),
              }}
            />
          );
        })}

        {/* Primary Selected Route Polyline (Bold glowing) */}
        {selectedRoute?.geometry && (
          <GeoJSON
            key={`primary-route-${selectedRoute.summary}-${selectedRoute.distance_meters}`}
            data={selectedRoute.geometry as unknown as GeoJsonObject}
            style={{
              color: getRouteColor(selectedRoute.congestion_level),
              weight: 6,
              opacity: 0.95,
            }}
          />
        )}

        {/* Intersections Layer */}
        {showIntersections &&
          intersections.map((intersection) => (
            <IntersectionMarker
              key={`int-${intersection.intersection_id}`}
              intersection={intersection}
              onSelect={(int) => {
                if (clickMode && onMapClick) {
                  onMapClick(int.latitude, int.longitude, int.name, clickMode);
                }
              }}
              onSetOrigin={() => onMapClick?.(intersection.latitude, intersection.longitude, intersection.name, "origin")}
              onSetDestination={() => onMapClick?.(intersection.latitude, intersection.longitude, intersection.name, "destination")}
            />
          ))}

        {/* Origin Pin */}
        {origin && Number.isFinite(origin.lat) && Number.isFinite(origin.lng) && (
          <Marker position={[origin.lat, origin.lng]} icon={createOriginIcon("A")}>
            <Popup>
              <div className="p-1 space-y-1 text-xs">
                <div className="font-bold text-emerald-400 flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5" />
                  <span>Origin (Start)</span>
                </div>
                <div className="text-white font-medium">{origin.name || "Custom Point"}</div>
                <div className="text-slate-400 font-mono text-[10px]">
                  {origin.lat.toFixed(4)}, {origin.lng.toFixed(4)}
                </div>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Destination Pin */}
        {destination && Number.isFinite(destination.lat) && Number.isFinite(destination.lng) && (
          <Marker position={[destination.lat, destination.lng]} icon={createDestinationIcon("B")}>
            <Popup>
              <div className="p-1 space-y-1 text-xs">
                <div className="font-bold text-rose-400 flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5" />
                  <span>Destination (End)</span>
                </div>
                <div className="text-white font-medium">{destination.name || "Custom Point"}</div>
                <div className="text-slate-400 font-mono text-[10px]">
                  {destination.lat.toFixed(4)}, {destination.lng.toFixed(4)}
                </div>
              </div>
            </Popup>
          </Marker>
        )}
        <RouteAlertLayer />
      </MapContainer>
    </div>
  );
};
