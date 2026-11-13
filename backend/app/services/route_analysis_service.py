import json
import hashlib
import logging
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Optional

import httpx
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.schemas.user_analysis import (
    CorridorDetail,
    CorridorIntersectionMatch,
    CorridorRoadMatch,
    CorridorZoneMatch,
    LocationSuggestion,
    RouteAIExplanation,
    RouteAlternative,
    RouteAnalysisRequest,
    RouteAnalysisResponse,
    RouteCoordinates,
    RouteTrafficObservation,
)
from backend.app.services.tomtom_traffic_service import tomtom_traffic_service
from ml.prediction.predictor import TrafficPredictor

logger = logging.getLogger("routex.route_analysis")

ROAD_ROUTE_CORRIDOR_METERS = 250
INTERSECTION_ROUTE_CORRIDOR_METERS = 350
TRAFFIC_ROUTE_CORRIDOR_METERS = 350
ASSET_OBSERVATION_RADIUS_METERS = 100
OSRM_CONNECTIVITY: dict[str, Any] = {"status": "unverified", "checked_at": None, "error": None}


def _make_route_id(
    origin: RouteCoordinates,
    destination: RouteCoordinates,
    geometry: dict[str, Any],
) -> str:
    canonical = json.dumps(
        {
            "origin": [origin.lat, origin.lng],
            "destination": [destination.lat, destination.lng],
            "geometry": geometry,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]

PRESET_LOCATIONS: list[LocationSuggestion] = [
    LocationSuggestion(
        id="LOC_INT_001",
        name="RouteX Test Intersection (INT_001)",
        lat=13.0827,
        lng=80.2707,
        source="DATABASE_INTERSECTION",
        description="Active monitored telemetry junction with CCTV and inductive loops",
    ),
    LocationSuggestion(
        id="LOC_ROAD_001",
        name="RouteX Main Corridor (ROAD_001)",
        lat=13.0820,
        lng=80.2700,
        source="DATABASE_ROAD",
        description="3-lane monitored arterial corridor with 50 km/h speed limit",
    ),
    LocationSuggestion(
        id="LOC_CENTRAL",
        name="Chennai Central Railway Junction",
        lat=13.0824,
        lng=80.2755,
        source="PRESET_HOTSPOT",
        description="High-density transit hub connecting north-south corridors",
    ),
    LocationSuggestion(
        id="LOC_EGMORE",
        name="Egmore Station Corridor",
        lat=13.0782,
        lng=80.2608,
        source="PRESET_HOTSPOT",
        description="Urban connector with heavy mixed traffic",
    ),
    LocationSuggestion(
        id="LOC_ANNA_NAGAR",
        name="Anna Nagar Roundtana",
        lat=13.0850,
        lng=80.2100,
        source="PRESET_HOTSPOT",
        description="Western residential-commercial traffic intersection",
    ),
    LocationSuggestion(
        id="LOC_TNAGAR",
        name="T. Nagar Panagal Park",
        lat=13.0405,
        lng=80.2337,
        source="PRESET_HOTSPOT",
        description="Intense retail and shopping traffic district",
    ),
    LocationSuggestion(
        id="LOC_GUINDY",
        name="Guindy Industrial Corridor",
        lat=13.0067,
        lng=80.2026,
        source="PRESET_HOTSPOT",
        description="Major arterial node linking GST road to central Chennai",
    ),
    LocationSuggestion(
        id="LOC_MARINA",
        name="Marina Beach Kamarajar Salai",
        lat=13.0500,
        lng=80.2824,
        source="PRESET_HOTSPOT",
        description="Coastal multi-lane boulevard",
    ),
]


def fetch_osrm_route(
    origin_lng: float,
    origin_lat: float,
    dest_lng: float,
    dest_lat: float,
    include_alternatives: bool = True,
) -> dict[str, Any]:
    """
    Queries real road route geometry and driving directions via public OSRM engine.
    """
    alt_param = "true" if include_alternatives else "false"
    OSRM_CONNECTIVITY["checked_at"] = datetime.now()
    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
        f"?overview=full&geometries=geojson&alternatives={alt_param}"
    )

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "RouteX-Traffic-Analysis/1.0"},
        )
        with urllib.request.urlopen(req, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("code") == "Ok" and data.get("routes"):
                OSRM_CONNECTIVITY.update(status="available", error=None)
                return data
            OSRM_CONNECTIVITY.update(status="unavailable", error=f"OSRM returned {data.get('code', 'no route')}.")
            return {"error": f"OSRM returned {data.get('code', 'no route')} without route geometry."}
    except Exception as exc:
        OSRM_CONNECTIVITY.update(status="unavailable", error=str(exc)[:180])
        logger.warning(f"OSRM routing query failed: {exc}")
        return {"error": f"OSRM request failed: {exc}"}



def fetch_tomtom_route(
    origin_lng: float,
    origin_lat: float,
    dest_lng: float,
    dest_lat: float,
) -> dict[str, Any]:
    """
    Fallback road routing using TomTom Routing API when OSRM is unreachable or times out.
    """
    if not tomtom_traffic_service.is_configured:
        return {"error": "TomTom routing fallback is not configured."}
    try:
        url = (
            f"https://api.tomtom.com/routing/1/calculateRoute/"
            f"{origin_lat},{origin_lng}:{dest_lat},{dest_lng}/json"
            f"?computeTravelTimeFor=all&traffic=true"
        )
        resp = httpx.get(
            url,
            params={"key": tomtom_traffic_service.api_key},
            timeout=6.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            routes = data.get("routes", [])
            if routes:
                r = routes[0]
                summary = r.get("summary", {})
                legs = r.get("legs", [])
                points = legs[0].get("points", []) if legs else []
                if points:
                    coords = [[p["longitude"], p["latitude"]] for p in points]
                    return {
                        "code": "Ok",
                        "routes": [
                            {
                                "distance": float(summary.get("lengthInMeters", 0.0)),
                                "duration": float(summary.get("travelTimeInSeconds", 0.0)),
                                "geometry": {"type": "LineString", "coordinates": coords},
                                "legs": [{"summary": "TomTom Verified Road Corridor"}],
                            }
                        ],
                    }
            return {"error": "TomTom Routing API returned no route geometry."}
        return {"error": f"TomTom Routing API returned HTTP {resp.status_code}."}
    except Exception as exc:
        logger.warning(tomtom_traffic_service._safe_request_error("routing", exc))
        return {"error": tomtom_traffic_service._safe_request_error("routing", exc)}


def fallback_postgis_route(
    db: Session,
    origin: RouteCoordinates,
    dest: RouteCoordinates,
) -> Optional[dict[str, Any]]:
    """
    Fallback routing against registered PostGIS road segments when external routing is unavailable.

    Only returns a route when origin and destination both lie near the same registered
    road geometry. Does not invent distance, duration, or a straight-line substitute.
    """
    query = text("""
        SELECT
            road_id,
            road_name,
            speed_limit,
            lanes,
            ST_AsGeoJSON(geometry) AS geom_json,
            ST_Length(geometry::geography) AS length_m
        FROM road_segments
        WHERE ST_DWithin(
            geometry::geography,
            ST_SetSRID(ST_MakePoint(:o_lng, :o_lat), 4326)::geography,
            500
        )
        AND ST_DWithin(
            geometry::geography,
            ST_SetSRID(ST_MakePoint(:d_lng, :d_lat), 4326)::geography,
            500
        )
        ORDER BY ST_Distance(
            geometry::geography,
            ST_SetSRID(ST_MakePoint(:o_lng, :o_lat), 4326)::geography
        )
        LIMIT 1
    """)
    try:
        row = db.execute(
            query,
            {
                "o_lng": origin.lng,
                "o_lat": origin.lat,
                "d_lng": dest.lng,
                "d_lat": dest.lat,
            },
        ).first()
    except Exception as exc:
        logger.warning(f"PostGIS fallback routing query failed: {exc}")
        return None

    if not row or not row.geom_json:
        return None

    try:
        geom = json.loads(row.geom_json)
        coords = geom.get("coordinates", [])
        length_m = float(row.length_m or 0.0)
        if len(coords) < 2 or length_m <= 0:
            return None

        speed_kmh = max(float(row.speed_limit or 30.0), 5.0)
        duration_s = length_m / (speed_kmh / 3.6)
        return {
            "code": "Ok",
            "routes": [
                {
                    "distance": length_m,
                    "duration": duration_s,
                    "geometry": geom,
                    "legs": [{"summary": f"Registered corridor {row.road_name}"}],
                }
            ],
        }
    except Exception:
        return None


def fetch_osrm_via_route(
    origin_lng: float,
    origin_lat: float,
    via_lng: float,
    via_lat: float,
    dest_lng: float,
    dest_lat: float,
) -> dict[str, Any]:
    """Queries real road route geometry via an intermediate road/junction waypoint."""
    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{origin_lng},{origin_lat};{via_lng},{via_lat};{dest_lng},{dest_lat}"
        f"?overview=full&geometries=geojson"
    )
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "RouteX-Traffic-Analysis/1.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("code") == "Ok" and data.get("routes"):
                return data
    except Exception as exc:
        logger.warning(f"OSRM via-point routing query failed: {exc}")
    return {}


def evaluate_corridor_telemetry(
    db: Session,
    geom_geojson: str,
) -> tuple[CorridorDetail, list[Any], bool, Optional[float], Optional[float], Optional[str], float]:
    """
    Evaluates PostGIS road segments, intersections, zones, and telemetry events
    along a specific route's geometry.
    """
    route_params = {
        "geom": geom_geojson,
        "road_corridor_m": ROAD_ROUTE_CORRIDOR_METERS,
        "intersection_corridor_m": INTERSECTION_ROUTE_CORRIDOR_METERS,
        "asset_observation_radius_m": ASSET_OBSERVATION_RADIUS_METERS,
    }

    # The envelope predicate uses the existing geometry GiST indexes. Geography
    # distance then applies the configured metre thresholds precisely.
    road_query = text("""
        WITH route AS (
            SELECT ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326) AS geometry
        )
        SELECT
            r.road_id,
            r.road_name,
            r.speed_limit,
            r.lanes,
            ST_AsGeoJSON(r.geometry) AS geometry,
            ST_Length(r.geometry::geography) AS length_meters,
            ST_Distance(r.geometry::geography, route.geometry::geography) AS distance_to_route_meters,
            CASE WHEN ST_Intersects(r.geometry, route.geometry) THEN 'INTERSECTS' ELSE 'NEARBY' END AS match_relation,
            road_obs.observed_average_speed,
            road_obs.observed_congestion,
            COALESCE(road_obs.observation_count, 0) AS observation_count,
            road_obs.last_observation_at,
            road_obs.observation_source
        FROM road_segments r
        CROSS JOIN route
        LEFT JOIN LATERAL (
            SELECT
                ROUND((AVG(recent.average_speed) FILTER (WHERE recent.source <> 'tomtom_traffic_incidents'))::numeric, 1) AS observed_average_speed,
                MODE() WITHIN GROUP (ORDER BY recent.congestion_level)
                    FILTER (WHERE recent.source <> 'tomtom_traffic_incidents') AS observed_congestion,
                COUNT(*)::int AS observation_count,
                MAX(recent.timestamp) AS last_observation_at,
                (ARRAY_AGG(recent.source ORDER BY recent.timestamp DESC))[1] AS observation_source
            FROM (
                SELECT
                    e.average_speed,
                    e.congestion_level,
                    e.timestamp,
                    CASE
                        WHEN jsonb_typeof(COALESCE(e.events::jsonb, '[]'::jsonb)) = 'array'
                            THEN COALESCE(e.events::jsonb -> 0 ->> 'source', 'routex_telemetry')
                        ELSE COALESCE(e.events::jsonb ->> 'source', 'routex_telemetry')
                    END AS source
                FROM traffic_stream_events e
                WHERE e.location IS NOT NULL
                  AND ST_DWithin(e.location::geography, r.geometry::geography, :asset_observation_radius_m)
                  AND ST_DWithin(e.location::geography, route.geometry::geography, :intersection_corridor_m)
                ORDER BY e.timestamp DESC
                LIMIT 30
            ) recent
        ) road_obs ON TRUE
        WHERE r.geometry && ST_Envelope(
                  ST_Transform(ST_Buffer(ST_Transform(route.geometry, 3857), :road_corridor_m), 4326)
              )
          AND ST_DWithin(r.geometry::geography, route.geometry::geography, :road_corridor_m)
        ORDER BY ST_Intersects(r.geometry, route.geometry) DESC, r.road_id
    """)
    matched_roads = []
    for r in db.execute(road_query, route_params):
        matched_roads.append(CorridorRoadMatch(
            road_id=r.road_id,
            road_name=r.road_name,
            speed_limit=float(r.speed_limit),
            lanes=int(r.lanes),
            geometry=json.loads(r.geometry) if r.geometry else None,
            length_meters=float(r.length_meters) if r.length_meters is not None else None,
            distance_to_route_meters=float(r.distance_to_route_meters) if r.distance_to_route_meters is not None else None,
            match_relation=r.match_relation,
            observed_average_speed=float(r.observed_average_speed) if r.observed_average_speed is not None else None,
            observed_congestion=r.observed_congestion,
            observation_count=int(r.observation_count or 0),
            last_observation_at=r.last_observation_at,
            observation_source=r.observation_source,
        ))

    int_query = text("""
        WITH route AS (
            SELECT ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326) AS geometry
        )
        SELECT
            i.intersection_id,
            i.name,
            i.latitude,
            i.longitude,
            ST_Distance(i.location::geography, route.geometry::geography) AS distance_to_route_meters,
            ARRAY(
                SELECT r.road_id
                FROM road_segments r
                WHERE ST_DWithin(r.geometry::geography, i.location::geography, :asset_observation_radius_m)
                  AND ST_DWithin(r.geometry::geography, route.geometry::geography, :road_corridor_m)
                ORDER BY ST_Distance(r.geometry::geography, i.location::geography), r.road_id
                LIMIT 8
            ) AS associated_road_ids,
            int_obs.observed_average_speed,
            int_obs.observed_congestion,
            COALESCE(int_obs.observation_count, 0) AS observation_count,
            int_obs.last_observation_at,
            int_obs.observation_source
        FROM intersections i
        CROSS JOIN route
        LEFT JOIN LATERAL (
            SELECT
                ROUND((AVG(recent.average_speed) FILTER (WHERE recent.source <> 'tomtom_traffic_incidents'))::numeric, 1) AS observed_average_speed,
                MODE() WITHIN GROUP (ORDER BY recent.congestion_level)
                    FILTER (WHERE recent.source <> 'tomtom_traffic_incidents') AS observed_congestion,
                COUNT(*)::int AS observation_count,
                MAX(recent.timestamp) AS last_observation_at,
                (ARRAY_AGG(recent.source ORDER BY recent.timestamp DESC))[1] AS observation_source
            FROM (
                SELECT
                    e.average_speed,
                    e.congestion_level,
                    e.timestamp,
                    CASE
                        WHEN jsonb_typeof(COALESCE(e.events::jsonb, '[]'::jsonb)) = 'array'
                            THEN COALESCE(e.events::jsonb -> 0 ->> 'source', 'routex_telemetry')
                        ELSE COALESCE(e.events::jsonb ->> 'source', 'routex_telemetry')
                    END AS source
                FROM traffic_stream_events e
                WHERE e.location IS NOT NULL
                  AND (e.intersection_id = i.intersection_id OR
                       ST_DWithin(e.location::geography, i.location::geography, :asset_observation_radius_m))
                  AND ST_DWithin(e.location::geography, route.geometry::geography, :intersection_corridor_m)
                ORDER BY e.timestamp DESC
                LIMIT 30
            ) recent
        ) int_obs ON TRUE
        WHERE i.location && ST_Envelope(
                  ST_Transform(ST_Buffer(ST_Transform(route.geometry, 3857), :intersection_corridor_m), 4326)
              )
          AND ST_DWithin(i.location::geography, route.geometry::geography, :intersection_corridor_m)
        ORDER BY ST_Distance(i.location::geography, route.geometry::geography), i.intersection_id
    """)
    matched_intersections = [
        CorridorIntersectionMatch(
            intersection_id=r.intersection_id,
            name=r.name,
            latitude=float(r.latitude),
            longitude=float(r.longitude),
            distance_to_route_meters=float(r.distance_to_route_meters) if r.distance_to_route_meters is not None else None,
            associated_road_ids=list(r.associated_road_ids or []),
            observed_average_speed=float(r.observed_average_speed) if r.observed_average_speed is not None else None,
            observed_congestion=r.observed_congestion,
            observation_count=int(r.observation_count or 0),
            last_observation_at=r.last_observation_at,
            observation_source=r.observation_source,
        )
        for r in db.execute(int_query, route_params)
    ]

    # 3. Traffic zones intersected
    zone_query = text("""
        SELECT zone_id, name, zone_type
        FROM traffic_zones
        WHERE ST_Intersects(
            geometry,
            ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)
        )
    """)
    matched_zones = [
        CorridorZoneMatch(
            zone_id=r.zone_id,
            name=r.name,
            zone_type=r.zone_type,
        )
        for r in db.execute(zone_query, {"geom": geom_geojson})
    ]

    # 4. Route-associated stream observations within the existing 350m corridor.
    events_query = text("""
        SELECT
            id,
            intersection_id,
            ST_Y(location::geometry) AS latitude,
            ST_X(location::geometry) AS longitude,
            total_vehicles,
            vehicle_types,
            lane_counts,
            direction_counts,
            average_speed,
            density,
            congestion_level,
            timestamp,
            events
        FROM traffic_stream_events
        WHERE location IS NOT NULL
        AND ST_DWithin(
            location::geography,
            ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)::geography,
            :intersection_corridor_m
        )
        ORDER BY timestamp DESC
        LIMIT 60
    """)
    stream_events = db.execute(events_query, route_params).fetchall()
    sample_count = len(stream_events)
    has_telemetry = sample_count > 0

    traffic_observations: list[RouteTrafficObservation] = []
    for event in stream_events:
        metadata: dict[str, Any] = {}
        if isinstance(event.events, list):
            metadata = next((item for item in event.events if isinstance(item, dict)), {})
        elif isinstance(event.events, dict):
            metadata = event.events
        source = str(metadata.get("source") or "routex_telemetry")
        traffic_observations.append(RouteTrafficObservation(
            id=int(event.id),
            intersection_id=event.intersection_id,
            latitude=float(event.latitude),
            longitude=float(event.longitude),
            total_vehicles=int(event.total_vehicles or 0),
            vehicle_types=event.vehicle_types or {},
            lane_counts=event.lane_counts or {},
            direction_counts=event.direction_counts or {},
            average_speed=float(event.average_speed or 0.0),
            free_flow_speed=(
                float(metadata["free_flow_speed"])
                if metadata.get("free_flow_speed") is not None
                else None
            ),
            density=float(event.density or 0.0),
            congestion_level=str(event.congestion_level or "UNKNOWN"),
            timestamp=event.timestamp,
            source=source,
            event_type=metadata.get("category_name") or metadata.get("event_type") or source,
            severity=int(metadata["magnitude_of_delay"]) if metadata.get("magnitude_of_delay") is not None else None,
            description=metadata.get("description"),
            delay_seconds=float(metadata["delay_seconds"]) if metadata.get("delay_seconds") is not None else None,
            details=metadata,
        ))

    speed_limit_ref = 50.0
    if matched_roads:
        speed_limit_ref = sum(r.speed_limit for r in matched_roads) / len(matched_roads)

    observed_avg_speed: Optional[float] = None
    observed_vehicles: Optional[float] = None
    observed_density: Optional[float] = None
    observed_congestion: Optional[str] = None
    active_incidents = 0
    inc_delay_sec = 0.0
    inc_summaries: list[str] = []

    if has_telemetry:
        flow_events = []
        incident_events = []
        for e in stream_events:
            raw_evts = e.events if isinstance(e.events, list) else ([e.events] if isinstance(e.events, dict) else [])
            src = raw_evts[0].get("source") if raw_evts and isinstance(raw_evts[0], dict) else None
            if src == "tomtom_traffic_incidents":
                incident_events.append(e)
            else:
                flow_events.append(e)

        effective_flow = flow_events if flow_events else [e for e in stream_events if e not in incident_events]
        if effective_flow:
            observed_avg_speed = round(sum(e.average_speed for e in effective_flow) / len(effective_flow), 1)
            observed_vehicles = round(sum(e.total_vehicles for e in effective_flow) / len(effective_flow), 1)
            observed_density = round(sum(e.density for e in effective_flow) / len(effective_flow), 3)

        for inc in incident_events:
            raw_evts = inc.events if isinstance(inc.events, list) else []
            if raw_evts and isinstance(raw_evts[0], dict):
                meta = raw_evts[0]
                inc_delay_sec += float(meta.get("delay_seconds", 0.0))
                desc = meta.get("description")
                road = meta.get("from_road") or meta.get("to_road")
                if desc:
                    summary_txt = f"{desc} on {road}" if road else desc
                    if summary_txt not in inc_summaries:
                        inc_summaries.append(summary_txt)
        active_incidents = len(incident_events)

        cong_counts: dict[str, int] = {}
        for e in effective_flow:
            cong_counts[e.congestion_level] = cong_counts.get(e.congestion_level, 0) + 1
        observed_congestion = max(cong_counts.keys(), key=lambda k: cong_counts[k]) if cong_counts else (
            "HIGH" if incident_events else "NO_TELEMETRY"
        )

        if active_incidents > 0 and (inc_delay_sec > 120 or any("Stationary" in s for s in inc_summaries)):
            observed_congestion = "HIGH"
        elif observed_density and observed_density > 0.5:
            observed_congestion = "HIGH"
        elif observed_density and observed_density > 0.25:
            observed_congestion = "MEDIUM"
    else:
        observed_congestion = "NO_TELEMETRY"

    latest_observation_at = max((o.timestamp for o in traffic_observations), default=None)
    observation_age_seconds = (
        max(0.0, (datetime.now() - latest_observation_at).total_seconds())
        if latest_observation_at is not None
        else None
    )
    if observation_age_seconds is None:
        observation_freshness = "UNAVAILABLE"
    elif observation_age_seconds <= 300:
        observation_freshness = "FRESH"
    elif observation_age_seconds <= 3600:
        observation_freshness = "RECENT"
    else:
        observation_freshness = "HISTORICAL"

    sources = {o.source for o in traffic_observations}
    if any(source.startswith("tomtom_") for source in sources) and len(sources) > 1:
        telemetry_source = "Mixed Route Telemetry"
    elif any(source.startswith("tomtom_") for source in sources):
        telemetry_source = "TomTom Live Traffic"
    elif "video_analysis" in sources:
        telemetry_source = "Video Analysis"
    else:
        telemetry_source = "RouteX Telemetry"

    corridor_detail = CorridorDetail(
        matched_roads=matched_roads,
        nearby_intersections=matched_intersections,
        traversed_zones=matched_zones,
        traffic_observations=traffic_observations,
        telemetry_status="AVAILABLE" if has_telemetry else "UNAVAILABLE",
        telemetry_sample_count=sample_count,
        observed_average_speed=observed_avg_speed,
        observed_free_flow_speed=(
            round(
                sum(o.free_flow_speed for o in traffic_observations if o.free_flow_speed is not None)
                / sum(1 for o in traffic_observations if o.free_flow_speed is not None),
                1,
            )
            if any(o.free_flow_speed is not None for o in traffic_observations)
            else None
        ),
        observed_total_vehicles=observed_vehicles,
        observed_density=observed_density,
        observed_congestion=observed_congestion,
        speed_limit_reference=round(speed_limit_ref, 1),
        latest_observation_at=latest_observation_at,
        observation_age_seconds=observation_age_seconds,
        observation_freshness=observation_freshness,
        active_incidents_count=active_incidents,
        incident_delay_seconds=round(inc_delay_sec, 1),
        telemetry_source=telemetry_source if has_telemetry else None,
        incidents_summary=inc_summaries[:5],
    )

    return (
        corridor_detail,
        stream_events,
        has_telemetry,
        observed_avg_speed,
        observed_density,
        observed_congestion,
        speed_limit_ref,
    )


def calculate_user_route(
    request: RouteAnalysisRequest,
    db: Session,
) -> RouteAnalysisResponse:
    """
    Performs full user-driven route analysis, integrating real road routing,
    corridor telemetry evaluation for all alternatives, and an evidence-based
    best route recommendation.
    """
    o_lat = request.origin.lat
    o_lng = request.origin.lng
    d_lat = request.destination.lat
    d_lng = request.destination.lng

    if abs(o_lat - d_lat) < 1e-6 and abs(o_lng - d_lng) < 1e-6:
        raise HTTPException(
            status_code=400,
            detail="Origin and destination must be different locations.",
        )

    # 1. Fetch real road geometry from routing service (OSRM primary, TomTom/PostGIS fallback)
    route_failures: list[str] = []
    osrm_data = fetch_osrm_route(o_lng, o_lat, d_lng, d_lat, request.include_alternatives)
    used_osrm_primary = bool(osrm_data and osrm_data.get("routes"))
    if not osrm_data or not osrm_data.get("routes"):
        route_failures.append((osrm_data or {}).get("error", "OSRM returned no route geometry."))
        osrm_data = fetch_tomtom_route(o_lng, o_lat, d_lng, d_lat)
    if not osrm_data or not osrm_data.get("routes"):
        route_failures.append((osrm_data or {}).get("error", "TomTom routing returned no route geometry."))
        # Attempt fallback to registered database corridor
        osrm_data = fallback_postgis_route(db, request.origin, request.destination)

    if not osrm_data or not osrm_data.get("routes"):
        raise HTTPException(
            status_code=503,
            detail=(
                "Routing calculation failed: "
                + " ".join(route_failures)
                + " No registered PostGIS road segment matches both endpoints within 500m."
            ),
        )

    raw_routes = list(osrm_data["routes"])
    primary_dist = float(raw_routes[0].get("distance", 0.0))

    # 1.1 If user requested alternatives and OSRM returned only 1 route, check for candidate arterial via-points
    approx_straight_km = (((o_lat - d_lat) ** 2 + (o_lng - d_lng) ** 2) ** 0.5) * 111.0
    if used_osrm_primary and request.include_alternatives and len(raw_routes) == 1 and approx_straight_km >= 1.2:
        # Only probe a bounded number of via candidates when OSRM successfully
        # returned the primary route. PostGIS/TomTom fallback routes must not
        # trigger a cascade of external OSRM requests during an outage.
        for preset in PRESET_LOCATIONS[:4]:
            dist_to_o = (((preset.lat - o_lat) ** 2 + (preset.lng - o_lng) ** 2) ** 0.5) * 111.0
            dist_to_d = (((preset.lat - d_lat) ** 2 + (preset.lng - d_lng) ** 2) ** 0.5) * 111.0
            if dist_to_o > 0.4 and dist_to_d > 0.4 and (dist_to_o + dist_to_d) < (approx_straight_km * 1.6):
                via_data = fetch_osrm_via_route(o_lng, o_lat, preset.lng, preset.lat, d_lng, d_lat)
                if via_data and via_data.get("routes"):
                    candidate_route = via_data["routes"][0]
                    cand_dist = float(candidate_route.get("distance", 0.0))
                    # Only accept if detour is meaningful (>100m) and not excessively convoluted (< 1.6x)
                    if cand_dist > (primary_dist + 100.0) and cand_dist < (primary_dist * 1.6):
                        candidate_route["legs"] = [{"summary": f"Via {preset.name}"}]
                        raw_routes.append(candidate_route)
                        break

    # 1.2 Ingest genuine live TomTom traffic flow and incidents along route geometry
    try:
        for raw in raw_routes:
            coords = raw.get("geometry", {}).get("coordinates", [])
            if coords:
                tomtom_traffic_service.ingest_route_observations(coords, db)
    except Exception as tt_err:
        logger.warning(f"TomTom route corridor ingestion error: {tt_err}")

    # 2. Evaluate corridor telemetry along EACH route alternative's geometry
    built_alternatives: list[RouteAlternative] = []
    route_measurements: dict[str, tuple[list[Any], bool, Optional[float], Optional[float], CorridorDetail]] = {}

    for idx, raw in enumerate(raw_routes):
        geom_json = json.dumps(raw["geometry"])
        (
            c_detail,
            s_events,
            has_telem,
            obs_speed,
            obs_density,
            obs_cong,
            speed_ref,
        ) = evaluate_corridor_telemetry(db, geom_json)

        dist_m = float(raw.get("distance", 0.0))
        dist_km = round(dist_m / 1000.0, 2)
        ff_sec = float(raw.get("duration", 0.0))
        ff_min = round(ff_sec / 60.0, 1)

        summary_name = f"Route Alternative {idx + 1}"
        if idx == 0:
            summary_name = "Primary Route"
        if raw.get("legs") and raw["legs"][0].get("summary"):
            summary_name = raw["legs"][0]["summary"] or summary_name

        route_id = _make_route_id(request.origin, request.destination, raw["geometry"])
        if not has_telem:
            alternative = RouteAlternative(
                route_id=route_id,
                summary=summary_name,
                distance_meters=round(dist_m, 1),
                distance_km=dist_km,
                free_flow_duration_seconds=round(ff_sec, 1),
                free_flow_duration_minutes=ff_min,
                traffic_duration_seconds=None,
                traffic_duration_minutes=None,
                delay_minutes=None,
                congestion_level="UNAVAILABLE",
                geometry=raw["geometry"],
                corridor_data_status="NO_TELEMETRY",
                corridor=c_detail,
                rank=idx + 1,
                is_recommended=False,
                incidents_count=0,
            )
        else:
            traffic_speed = max(10.0, obs_speed or speed_ref)
            speed_factor = max(0.8, speed_ref / traffic_speed)
            inc_delay = c_detail.incident_delay_seconds or 0.0
            traffic_sec = round((ff_sec * speed_factor) + inc_delay, 1)
            traffic_min = round(traffic_sec / 60.0, 1)
            delay_min = max(0.0, round((traffic_sec - ff_sec) / 60.0, 1))

            alternative = RouteAlternative(
                route_id=route_id,
                summary=summary_name,
                distance_meters=round(dist_m, 1),
                distance_km=dist_km,
                free_flow_duration_seconds=round(ff_sec, 1),
                free_flow_duration_minutes=ff_min,
                traffic_duration_seconds=traffic_sec,
                traffic_duration_minutes=traffic_min,
                delay_minutes=delay_min,
                congestion_level=obs_cong or "LOW",
                geometry=raw["geometry"],
                corridor_data_status="LIVE_TELEMETRY",
                corridor=c_detail,
                rank=idx + 1,
                is_recommended=False,
                incidents_count=c_detail.active_incidents_count,
            )
        built_alternatives.append(alternative)
        route_measurements[route_id] = (s_events, has_telem, obs_speed, obs_density, c_detail)

    # 3. Calculate consistent, explainable best route recommendation
    # Score each alternative: travel time + congestion penalty + distance factor
    def compute_route_score(r: RouteAlternative) -> float:
        eff_time = r.traffic_duration_minutes if r.traffic_duration_minutes is not None else r.free_flow_duration_minutes
        cong_penalty = 0.0
        if r.congestion_level == "HIGH":
            cong_penalty = 5.0
        elif r.congestion_level == "MEDIUM":
            cong_penalty = 2.0
        # Distance tie-breaker
        return eff_time + cong_penalty + (r.distance_km * 0.05)

    scored_routes = sorted(built_alternatives, key=compute_route_score)
    any_has_telemetry = any(r.corridor_data_status == "LIVE_TELEMETRY" for r in built_alternatives)

    for rank_idx, r in enumerate(scored_routes, start=1):
        r.rank = rank_idx
        if rank_idx == 1:
            r.is_recommended = True
            if any_has_telemetry and r.corridor_data_status == "LIVE_TELEMETRY":
                time_str = f"{r.traffic_duration_minutes} min"
                delay_str = f" (+{r.delay_minutes}m delay)" if r.delay_minutes else ""
                r.recommendation_reason = (
                    f"Optimal travel efficiency: estimated time {time_str}{delay_str} with verified {r.congestion_level} congestion."
                )
            else:
                r.recommendation_reason = (
                    f"Shortest base travel path: {r.distance_km} km in {r.free_flow_duration_minutes} min base driving time."
                )
        else:
            r.is_recommended = False
            r.recommendation_reason = (
                f"Alternative option: {r.distance_km} km ({r.traffic_duration_minutes or r.free_flow_duration_minutes} min)."
            )

    best_route = scored_routes[0]
    rec_basis = "TRAFFIC_AWARE_OPTIMIZED" if (any_has_telemetry and best_route.corridor_data_status == "LIVE_TELEMETRY") else "FREE_FLOW_BASE"

    if len(built_alternatives) == 1:
        if best_route.corridor_data_status == "LIVE_TELEMETRY":
            rec_explanation = (
                f"Recommended as the direct route: {best_route.distance_km} km with an estimated driving time of "
                f"{best_route.traffic_duration_minutes} min (verified {best_route.congestion_level} congestion from live corridor telemetry)."
            )
        else:
            rec_explanation = (
                f"Recommended as the direct driving path: {best_route.distance_km} km with a base driving duration of "
                f"{best_route.free_flow_duration_minutes} min. Live sensor telemetry is unavailable along this corridor to evaluate traffic delays."
            )
    else:
        if rec_basis == "TRAFFIC_AWARE_OPTIMIZED":
            rec_explanation = (
                f"Route '{best_route.summary}' is ranked #1: lowest overall travel cost with {best_route.traffic_duration_minutes} min "
                f"estimated driving time and {best_route.congestion_level} congestion, outperforming available alternatives."
            )
        else:
            rec_explanation = (
                f"Route '{best_route.summary}' is ranked #1 based on shortest road distance ({best_route.distance_km} km) "
                f"and {best_route.free_flow_duration_minutes} min base driving time. Live telemetry is unavailable for dynamic traffic adjustment."
            )

    # 4. Preserve route-specific corridor data and AI analysis for every option.
    now = datetime.now()
    predictor: Optional[TrafficPredictor] = None
    for alternative in built_alternatives:
        events, has_telem, avg_speed, density, corridor = route_measurements[alternative.route_id]
        if not has_telem or avg_speed is None or density is None or not events:
            alternative.ai_prediction = RouteAIExplanation(
                status="INSUFFICIENT_DATA",
                explanation=(
                    "No valid traffic flow observations were found along this route corridor. "
                    "RouteX AI predictions require valid corridor observations."
                ),
            )
            continue

        try:
            if predictor is None:
                predictor = TrafficPredictor()
            mean_vehicles = int(sum(e.total_vehicles for e in events) / len(events))
            ai_input = {
                "total_vehicles": mean_vehicles,
                "average_speed": avg_speed,
                "density": density,
                "hour": now.hour,
                "day_of_week": now.weekday(),
                "minute": now.minute,
            }
            prediction = predictor.predict(ai_input)
            provider_name = corridor.telemetry_source or "RouteX sensor telemetry"
            alternative.ai_prediction = RouteAIExplanation(
                status="AVAILABLE",
                model_name="routex_production_predictor",
                predicted_congestion=prediction.get("predicted_congestion"),
                prediction_confidence=prediction.get("prediction_confidence"),
                predicted_vehicle_count=prediction.get("predicted_vehicle_count"),
                features_used=ai_input,
                explanation=(
                    f"Forecast derived from {len(events)} {provider_name} observations along this route. "
                    f"Features: avg speed {avg_speed} km/h, density {density:.2f}, volume {mean_vehicles} veh."
                ),
            )
        except Exception as pred_err:
            alternative.ai_prediction = RouteAIExplanation(
                status="INSUFFICIENT_DATA",
                explanation=f"AI model inference encountered an error: {str(pred_err)}",
            )

    primary_stream_events, primary_has_telemetry, primary_avg_speed, primary_density, primary_corridor = route_measurements[best_route.route_id]
    ai_explanation = best_route.ai_prediction or RouteAIExplanation(
        status="INSUFFICIENT_DATA",
        explanation="No route-specific AI analysis is available.",
    )

    freshness_note = (
        f"Corridor analyzed using {len(primary_stream_events)} active telemetry observations ({primary_corridor.telemetry_source if primary_corridor else 'TomTom'})."
        if primary_has_telemetry
        else "No telemetry sensors or live provider coverage along this corridor. Displaying free-flow road geometry."
    )

    return RouteAnalysisResponse(
        origin=request.origin,
        destination=request.destination,
        selected_route=best_route,
        alternatives=built_alternatives,
        corridor=primary_corridor
        or CorridorDetail(
            matched_roads=[],
            nearby_intersections=[],
            traversed_zones=[],
            telemetry_status="UNAVAILABLE",
            telemetry_sample_count=0,
            observed_average_speed=None,
            observed_density=None,
            observed_congestion="NO_TELEMETRY",
            speed_limit_reference=50.0,
        ),
        ai_prediction=ai_explanation,
        analyzed_at=datetime.now(),
        data_freshness_note=freshness_note,
        recommended_route_summary=best_route.summary,
        recommendation_explanation=rec_explanation,
        recommendation_basis=rec_basis,
        traffic_provider=primary_corridor.telemetry_source if primary_corridor and primary_corridor.telemetry_source else "TomTom Traffic API",
    )


def search_locations(query: str, db: Session) -> list[LocationSuggestion]:
    """
    Returns location suggestions matching database intersections, roads, and preset hotspots.
    """
    clean_q = query.strip().lower()
    results: list[LocationSuggestion] = []

    # 1. Search database intersections
    try:
        int_res = db.execute(
            text("""
                SELECT intersection_id, name, latitude, longitude
                FROM intersections
                WHERE name ILIKE :q OR intersection_id ILIKE :q
                LIMIT 5
            """),
            {"q": f"%{clean_q}%"},
        ).fetchall()
        for r in int_res:
            results.append(
                LocationSuggestion(
                    id=f"INT_{r.intersection_id}",
                    name=r.name,
                    lat=float(r.latitude),
                    lng=float(r.longitude),
                    source="DATABASE_INTERSECTION",
                    description=f"RouteX monitored junction ({r.intersection_id})",
                )
            )
    except Exception:
        pass

    # 2. Search database roads
    try:
        road_res = db.execute(
            text("""
                SELECT road_id, road_name, speed_limit,
                       ST_Y(ST_Centroid(geometry)) AS lat,
                       ST_X(ST_Centroid(geometry)) AS lng
                FROM road_segments
                WHERE road_name ILIKE :q OR road_id ILIKE :q
                LIMIT 5
            """),
            {"q": f"%{clean_q}%"},
        ).fetchall()
        for r in road_res:
            if r.lat is not None and r.lng is not None:
                results.append(
                    LocationSuggestion(
                        id=f"ROAD_{r.road_id}",
                        name=r.road_name,
                        lat=float(r.lat),
                        lng=float(r.lng),
                        source="DATABASE_ROAD",
                        description=f"Monitored corridor ({r.road_id}) - {r.speed_limit} km/h",
                    )
                )
    except Exception:
        pass

    # 3. Match presets
    for preset in PRESET_LOCATIONS:
        if clean_q in preset.name.lower() or clean_q in (preset.description or "").lower():
            if not any(item.id == preset.id for item in results):
                results.append(preset)

    # If query is empty or short, return top presets
    if not clean_q:
        return PRESET_LOCATIONS[:6]

    return results
