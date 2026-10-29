import json
import logging
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Optional

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
)
from ml.prediction.predictor import TrafficPredictor

logger = logging.getLogger("routex.route_analysis")

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
                return data
    except Exception as exc:
        logger.warning(f"OSRM routing query failed: {exc}")

    return {}


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
    # 1. Road segments within 250m corridor
    road_query = text("""
        SELECT road_id, road_name, speed_limit, lanes
        FROM road_segments
        WHERE ST_DWithin(
            geometry::geography,
            ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)::geography,
            250
        )
    """)
    matched_roads = [
        CorridorRoadMatch(
            road_id=r.road_id,
            road_name=r.road_name,
            speed_limit=float(r.speed_limit),
            lanes=int(r.lanes),
        )
        for r in db.execute(road_query, {"geom": geom_geojson})
    ]

    # 2. Intersections within 350m corridor
    int_query = text("""
        SELECT intersection_id, name, latitude, longitude
        FROM intersections
        WHERE ST_DWithin(
            location::geography,
            ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)::geography,
            350
        )
    """)
    matched_intersections = [
        CorridorIntersectionMatch(
            intersection_id=r.intersection_id,
            name=r.name,
            latitude=float(r.latitude),
            longitude=float(r.longitude),
        )
        for r in db.execute(int_query, {"geom": geom_geojson})
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

    # 4. Stream events within 350m corridor
    events_query = text("""
        SELECT
            total_vehicles,
            average_speed,
            density,
            congestion_level,
            timestamp
        FROM traffic_stream_events
        WHERE location IS NOT NULL
        AND ST_DWithin(
            location::geography,
            ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)::geography,
            350
        )
        ORDER BY timestamp DESC
        LIMIT 60
    """)
    stream_events = db.execute(events_query, {"geom": geom_geojson}).fetchall()
    sample_count = len(stream_events)
    has_telemetry = sample_count > 0

    speed_limit_ref = 50.0
    if matched_roads:
        speed_limit_ref = sum(r.speed_limit for r in matched_roads) / len(matched_roads)

    observed_avg_speed: Optional[float] = None
    observed_density: Optional[float] = None
    observed_congestion: Optional[str] = None

    if has_telemetry:
        observed_avg_speed = round(sum(e.average_speed for e in stream_events) / sample_count, 1)
        observed_density = round(sum(e.density for e in stream_events) / sample_count, 3)
        cong_counts: dict[str, int] = {}
        for e in stream_events:
            cong_counts[e.congestion_level] = cong_counts.get(e.congestion_level, 0) + 1
        observed_congestion = max(cong_counts.keys(), key=lambda k: cong_counts[k])
    else:
        observed_congestion = "NO_TELEMETRY"

    corridor_detail = CorridorDetail(
        matched_roads=matched_roads,
        nearby_intersections=matched_intersections,
        traversed_zones=matched_zones,
        telemetry_status="AVAILABLE" if has_telemetry else "UNAVAILABLE",
        telemetry_sample_count=sample_count,
        observed_average_speed=observed_avg_speed,
        observed_density=observed_density,
        observed_congestion=observed_congestion,
        speed_limit_reference=round(speed_limit_ref, 1),
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

    # 1. Fetch real road geometry from routing service
    osrm_data = fetch_osrm_route(o_lng, o_lat, d_lng, d_lat, request.include_alternatives)
    if not osrm_data or not osrm_data.get("routes"):
        # Attempt fallback to registered database corridor
        osrm_data = fallback_postgis_route(db, request.origin, request.destination)

    if not osrm_data or not osrm_data.get("routes"):
        raise HTTPException(
            status_code=503,
            detail=(
                "Routing calculation failed: Unable to compute real road geometry between the specified "
                "origin and destination. Please check the coordinates or retry."
            ),
        )

    raw_routes = list(osrm_data["routes"])
    primary_dist = float(raw_routes[0].get("distance", 0.0))

    # 1.1 If user requested alternatives and OSRM returned only 1 route, check for candidate arterial via-points
    approx_straight_km = (((o_lat - d_lat) ** 2 + (o_lng - d_lng) ** 2) ** 0.5) * 111.0
    if request.include_alternatives and len(raw_routes) == 1 and approx_straight_km >= 1.2:
        for preset in PRESET_LOCATIONS:
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

    # 2. Evaluate corridor telemetry along EACH route alternative's geometry
    built_alternatives: list[RouteAlternative] = []
    primary_corridor: Optional[CorridorDetail] = None
    primary_stream_events: list[Any] = []
    primary_has_telemetry: bool = False
    primary_avg_speed: Optional[float] = None
    primary_density: Optional[float] = None

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

        if idx == 0:
            primary_corridor = c_detail
            primary_stream_events = s_events
            primary_has_telemetry = has_telem
            primary_avg_speed = obs_speed
            primary_density = obs_density

        dist_m = float(raw.get("distance", 0.0))
        dist_km = round(dist_m / 1000.0, 2)
        ff_sec = float(raw.get("duration", 0.0))
        ff_min = round(ff_sec / 60.0, 1)

        summary_name = f"Route Alternative {idx + 1}"
        if idx == 0:
            summary_name = "Primary Route"
        if raw.get("legs") and raw["legs"][0].get("summary"):
            summary_name = raw["legs"][0]["summary"] or summary_name

        if not has_telem:
            built_alternatives.append(
                RouteAlternative(
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
                    rank=idx + 1,
                    is_recommended=False,
                )
            )
        else:
            traffic_speed = max(10.0, obs_speed or speed_ref)
            speed_factor = max(0.8, speed_ref / traffic_speed)
            traffic_sec = round(ff_sec * speed_factor, 1)
            traffic_min = round(traffic_sec / 60.0, 1)
            delay_min = max(0.0, round((traffic_sec - ff_sec) / 60.0, 1))

            built_alternatives.append(
                RouteAlternative(
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
                    rank=idx + 1,
                    is_recommended=False,
                )
            )

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

    # 4. Integrate AI / ML prediction models for the selected route
    ai_explanation: RouteAIExplanation
    now = datetime.now()

    if primary_has_telemetry and primary_avg_speed is not None and primary_density is not None:
        try:
            predictor = TrafficPredictor()
            mean_vehicles = int(sum(e.total_vehicles for e in primary_stream_events) / len(primary_stream_events))
            ai_input = {
                "total_vehicles": mean_vehicles,
                "average_speed": primary_avg_speed,
                "density": primary_density,
                "hour": now.hour,
                "day_of_week": now.weekday(),
                "minute": now.minute,
            }
            pred = predictor.predict(ai_input)

            ai_explanation = RouteAIExplanation(
                status="AVAILABLE",
                model_name="routex_production_predictor",
                predicted_congestion=pred.get("predicted_congestion"),
                prediction_confidence=pred.get("prediction_confidence"),
                predicted_vehicle_count=pred.get("predicted_vehicle_count"),
                features_used=ai_input,
                explanation=(
                    f"Forecast derived from {len(primary_stream_events)} stream telemetry observations along corridor. "
                    f"Features: avg speed {primary_avg_speed} km/h, density {primary_density:.2f}, "
                    f"volume {mean_vehicles} veh."
                ),
            )
        except Exception as pred_err:
            ai_explanation = RouteAIExplanation(
                status="INSUFFICIENT_DATA",
                explanation=f"AI model inference encountered an error: {str(pred_err)}",
            )
    else:
        ai_explanation = RouteAIExplanation(
            status="INSUFFICIENT_DATA",
            explanation=(
                "No live or historical telemetry records found along this corridor within 350 meters. "
                "RouteX AI models require sensor observations to construct input features."
            ),
        )

    freshness_note = (
        f"Corridor analyzed using {len(primary_stream_events)} active database telemetry events."
        if primary_has_telemetry
        else "No telemetry sensors on this corridor. Displaying free-flow road geometry and base distances."
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
