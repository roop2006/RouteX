import { Link } from "react-router-dom";
import { CircleMarker, Popup, GeoJSON } from "react-leaflet";
import type { GeoJsonObject } from "geojson";
import { useSelectedRoute } from "../../contexts/selectedRouteContext";
import { useRouteAlerts } from "../../hooks/useAlerts";
import { formatTimestamp } from "../../utils/formatters";

export function RouteAlertLayer({ showRoute = false }: { showRoute?: boolean }) {
  const route = useSelectedRoute();
  const query = useRouteAlerts(route.routeId, route.geometry);
  if (!route.routeId || !route.geometry) return null;
  const seen = new Set<string>();
  const matches = (query.data?.alerts ?? []).filter(({ alert }) => {
    const key = `${alert.source}:${alert.source_event_id || alert.id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  return <>
    {showRoute && <GeoJSON key={route.routeId} data={route.geometry as GeoJsonObject} style={{ color: "#3b82f6", weight: 5 }} />}
    {matches.map((match) => {
      const alert = match.alert;
      const lat = match.marker_latitude ?? alert.latitude;
      const lng = match.marker_longitude ?? alert.longitude;
      if (lat == null || lng == null) return null;
      return <CircleMarker key={`${route.routeId}:${alert.id}`} center={[lat, lng]} radius={9} pathOptions={{ color: "#fff", fillColor: alert.severity === "CRITICAL" ? "#e11d48" : "#f59e0b", fillOpacity: 1, weight: 2 }}>
        <Popup><div className="space-y-1 text-xs" data-alert-id={alert.id}>
          <strong>{alert.title} · {alert.severity}</strong>
          <p>{alert.description}</p><p>{alert.road_name}</p>
          <p>{alert.status} · {query.data?.status === "AVAILABLE" ? "Reported" : "Last known; provider unavailable"}</p>
          <p>{Math.round(match.distance_to_route_meters ?? 0)} m from route</p>
          <p>{alert.source} · {formatTimestamp(alert.updated_at)}</p>
          <Link to="/alerts">Inspect route alerts</Link>
        </div></Popup>
      </CircleMarker>;
    })}
  </>;
}
