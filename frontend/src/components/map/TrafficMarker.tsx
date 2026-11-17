import React from "react";
import { Marker, Popup } from "react-leaflet";
import L from "leaflet";
import { formatTimeOnly, formatSpeed, formatDensity } from "../../utils/formatters";
import { getCongestionBadgeClass } from "../../utils/congestion";
import type { NearbyTrafficEvent, Intersection } from "../../types/geography";

function createCongestionMarkerIcon(level: string, vehicleCount?: number | null): L.DivIcon {
  const upper = (level || "UNKNOWN").toUpperCase();
  const color =
    upper === "HIGH" ? "#ef4444" : upper === "MEDIUM" ? "#f59e0b" : upper === "LOW" ? "#10b981" : "#64748b";
  const glow =
    upper === "HIGH"
      ? "rgba(239, 68, 68, 0.4)"
      : upper === "MEDIUM"
      ? "rgba(245, 158, 11, 0.4)"
      : "rgba(16, 185, 129, 0.4)";

  return L.divIcon({
    className: "custom-traffic-pin",
    html: `
      <div style="position: relative; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;">
        <span style="position: absolute; width: 100%; height: 100%; border-radius: 50%; background: ${glow}; opacity: 0.75;"></span>
        <div style="position: relative; width: 22px; height: 22px; border-radius: 50%; background: ${color}; border: 2px solid #0f172a; display: flex; align-items: center; justify-content: center; color: white; font-size: 10px; font-weight: 700; box-shadow: 0 4px 8px rgba(0,0,0,0.5);">
          ${vehicleCount != null ? vehicleCount : "•"}
        </div>
      </div>
    `,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -14],
  });
}

function createIntersectionMarkerIcon(name: string): L.DivIcon {
  return L.divIcon({
    className: "custom-intersection-pin",
    html: `
      <div style="position: relative; width: 26px; height: 26px; border-radius: 8px; background: #6366f1; border: 2px solid #ffffff; display: flex; align-items: center; justify-content: center; color: white; font-size: 12px; font-weight: 800; box-shadow: 0 4px 10px rgba(0,0,0,0.5);" title="${name}">
        ✕
      </div>
    `,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    popupAnchor: [0, -13],
  });
}

interface EventMarkerProps {
  event: NearbyTrafficEvent;
  onSelect?: (event: NearbyTrafficEvent) => void;
}

export const TrafficEventMarker: React.FC<EventMarkerProps> = ({ event, onSelect }) => {
  if (isNaN(event.latitude) || isNaN(event.longitude)) return null;

  return (
    <Marker
      position={[event.latitude, event.longitude]}
      icon={createCongestionMarkerIcon(event.congestion_level, event.total_vehicles)}
      eventHandlers={{
        click: () => onSelect?.(event),
      }}
    >
      <Popup>
        <div className="p-1 space-y-2 text-xs">
          <div className="flex items-center justify-between gap-2 border-b border-slate-700/60 pb-1.5">
            <span className="font-bold text-white">Event #{event.id}</span>
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${getCongestionBadgeClass(event.congestion_level)}`}>
              {event.congestion_level}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-slate-300">
            <div>
              <span className="text-slate-400 block text-[10px]">Vehicles</span>
              <span className="font-mono font-bold text-white text-sm">{event.total_vehicles ?? "Unavailable"}</span>
            </div>
            <div>
              <span className="text-slate-400 block text-[10px]">Speed</span>
              <span className="font-mono font-bold text-white">{formatSpeed(event.average_speed)}</span>
            </div>
            <div>
              <span className="text-slate-400 block text-[10px]">Density</span>
              <span className="font-mono text-white">{formatDensity(event.density)}</span>
            </div>
            <div>
              <span className="text-slate-400 block text-[10px]">Intersection</span>
              <span className="font-mono text-slate-200">{event.intersection_id || "N/A"}</span>
            </div>
          </div>

          <div className="text-[10px] text-slate-400 border-t border-slate-700/40 pt-1">
            Time: {formatTimeOnly(event.timestamp)}
          </div>
        </div>
      </Popup>
    </Marker>
  );
};

interface IntersectionMarkerProps {
  intersection: Intersection;
  onSelect?: (intersection: Intersection) => void;
  onSetOrigin?: (intersection: Intersection) => void;
  onSetDestination?: (intersection: Intersection) => void;
}

export const IntersectionMarker: React.FC<IntersectionMarkerProps> = ({
  intersection,
  onSelect,
  onSetOrigin,
  onSetDestination,
}) => {
  if (isNaN(intersection.latitude) || isNaN(intersection.longitude)) return null;

  return (
    <Marker
      position={[intersection.latitude, intersection.longitude]}
      icon={createIntersectionMarkerIcon(intersection.name)}
      eventHandlers={{
        click: () => onSelect?.(intersection),
      }}
    >
      <Popup>
        <div className="p-1 space-y-1.5 text-xs">
          <div className="font-bold text-indigo-300 border-b border-slate-700/60 pb-1">
            {intersection.name}
          </div>
          <div className="text-slate-300 text-[11px]">
            ID: <span className="font-mono text-white">{intersection.intersection_id}</span>
          </div>
          <div className="text-slate-400 text-[10px] font-mono">
            Lat: {intersection.latitude.toFixed(4)}, Lng: {intersection.longitude.toFixed(4)}
          </div>
          {(onSetOrigin || onSetDestination) && (
            <div className="flex items-center gap-1.5 pt-1 border-t border-slate-700/60">
              {onSetOrigin && (
                <button
                  type="button"
                  onClick={() => onSetOrigin(intersection)}
                  className="px-2 py-0.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-[10px] font-semibold transition-colors"
                >
                  Set Origin
                </button>
              )}
              {onSetDestination && (
                <button
                  type="button"
                  onClick={() => onSetDestination(intersection)}
                  className="px-2 py-0.5 bg-rose-600 hover:bg-rose-500 text-white rounded text-[10px] font-semibold transition-colors"
                >
                  Set Destination
                </button>
              )}
            </div>
          )}
        </div>
      </Popup>
    </Marker>
  );
};
