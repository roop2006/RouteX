"""
TomTom Live Traffic Service for RouteX.
Integrates TomTom Traffic Flow and Traffic Incidents APIs with:
- Strict API key security (never exposed to frontend, masked in logs)
- Intelligent coordinate rounding and TTL caching to prevent quota exhaustion
- Route-aware corridor sampling and incident spatial association
- Ingestion into PostgreSQL / PostGIS with strict source provenance ('tomtom_traffic_flow', 'tomtom_traffic_incidents')
- Explicit feature extraction for RouteX ML prediction models
"""
from datetime import datetime, timedelta
import json
import logging
import math
import os
import threading
import time
from typing import Any, Optional

from geoalchemy2.elements import WKTElement
import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.geo_config import (
    DEFAULT_CAMERA_LATITUDE,
    DEFAULT_CAMERA_LONGITUDE,
    POSTGIS_SRID,
)
from backend.app.models.traffic_stream_event import TrafficStreamEvent

logger = logging.getLogger("routex.tomtom_service")

# Mapping TomTom iconCategory to human-readable labels
TOMTOM_ICON_CATEGORIES = {
    0: "Unknown",
    1: "Accident",
    2: "Fog",
    3: "Dangerous Conditions",
    4: "Rain",
    5: "Ice",
    6: "Jam / Stationary Traffic",
    7: "Lane Closed",
    8: "Road Closed",
    9: "Road Works",
    10: "Wind",
    11: "Flooding",
    14: "Broken Down Vehicle",
}

# Mapping magnitude of delay
TOMTOM_DELAY_MAGNITUDE = {
    0: "Unknown",
    1: "Minor",
    2: "Moderate",
    3: "Major",
    4: "Undefined",
}


class TomTomTrafficService:
    def __init__(self):
        self.api_key: Optional[str] = settings.tomtom_api_key or os.getenv("TOMTOM_API_KEY")
        self.base_url: str = settings.tomtom_traffic_base_url.rstrip("/")
        self.cache_ttl: int = settings.tomtom_cache_ttl_seconds or 300
        self.incidents_ttl: int = 600  # 10 minutes cache for incidents

        # In-memory thread-safe cache
        self._flow_cache: dict[str, tuple[dict[str, Any], datetime]] = {}
        self._incidents_cache: dict[str, tuple[list[dict[str, Any]], datetime]] = {}
        self._tile_cache: dict[str, tuple[bytes, datetime]] = {}
        self._lock = threading.Lock()
        self._flow_inflight: dict[str, threading.Event] = {}
        self._incident_inflight: dict[str, threading.Event] = {}
        self._http_client = httpx.Client(
            timeout=httpx.Timeout(connect=2.0, read=4.0, write=2.0, pool=1.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            trust_env=True,
        )
        self.last_flow_error: Optional[str] = None
        self.last_incident_error: Optional[str] = None
        self.last_flow_checked_at: Optional[datetime] = None
        self.last_incident_checked_at: Optional[datetime] = None
        self.flow_connectivity_status = "unverified"
        self.incident_connectivity_status = "unverified"

        # Telemetry and circuit breaker
        self._circuit_breaker_until: Optional[datetime] = None
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "rate_limit_hits": 0,
            "errors": 0,
        }

    @property
    def is_configured(self) -> bool:
        """Returns True if a non-empty API key is available."""
        return bool(self.api_key and len(self.api_key.strip()) > 8)

    @property
    def masked_key(self) -> str:
        """Returns a masked representation of the API key for diagnostic logging."""
        if not self.api_key:
            return "UNCONFIGURED"
        if len(self.api_key) <= 8:
            return "***"
        return f"{self.api_key[:4]}...{self.api_key[-4:]}"

    def _safe_request_error(self, operation: str, error: Exception) -> str:
        message = str(error)
        if self.api_key:
            message = message.replace(self.api_key, "***")
        return f"TomTom {operation} request failed: {message or error.__class__.__name__}"

    def _is_rate_limited(self) -> bool:
        """Checks whether the circuit breaker is active after an HTTP 429."""
        if self._circuit_breaker_until and datetime.now() < self._circuit_breaker_until:
            return True
        self._circuit_breaker_until = None
        return False

    def _trigger_backoff(self, seconds: int = 60):
        """Activates circuit breaker for specified seconds following a 429 rate limit."""
        self._circuit_breaker_until = datetime.now() + timedelta(seconds=seconds)
        self.stats["rate_limit_hits"] += 1
        logger.warning(
            f"TomTom API rate limit encountered. Pausing external requests for {seconds}s."
        )

    def _request_with_retry(self, url: str, params: dict[str, Any], operation: str):
        """Reuse pooled connections and retry transient network/gateway errors once."""
        for attempt in range(2):
            try:
                response = self._http_client.get(url, params=params)
                if response.status_code not in (502, 503, 504) or attempt == 1:
                    return response
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == 1:
                    raise
            time.sleep(0.2 * (attempt + 1))
        raise RuntimeError(f"TomTom {operation} request did not complete")

    @staticmethod
    def _cache_age(data: dict[str, Any], now: datetime) -> int | None:
        try:
            retrieved = datetime.fromisoformat(str(data["retrieved_at"]).replace("Z", "+00:00"))
            if retrieved.tzinfo is not None:
                retrieved = retrieved.replace(tzinfo=None)
            return max(0, int((now - retrieved).total_seconds()))
        except (KeyError, TypeError, ValueError):
            return None

    # -------------------------------------------------------------------------
    # 1. Traffic Flow Segment Data (Point-based Road Inspection)
    # -------------------------------------------------------------------------
    def get_flow_segment_data(
        self,
        lat: float,
        lng: float,
        zoom: int = 10,
        style: str = "relative-delay",
    ) -> Optional[dict[str, Any]]:
        """
        Retrieves real-time traffic flow speed, free-flow speed, travel time,
        and congestion level for a road segment passing through (lat, lng).
        Uses coordinate rounding (3 decimals ~ 110m) and TTL caching.
        """
        if not self.is_configured:
            self.last_flow_error = "TOMTOM_API_KEY is not configured."
            return None

        # Round coordinates for high-efficiency cache reuse
        grid_lat = round(lat, 3)
        grid_lng = round(lng, 3)
        cache_key = f"{grid_lat}:{grid_lng}:{zoom}:{style}"

        now = datetime.now()
        stale_data = None
        wait_for: threading.Event | None = None
        owner_event: threading.Event | None = None
        with self._lock:
            if cache_key in self._flow_cache:
                data, expire_at = self._flow_cache[cache_key]
                if now < expire_at:
                    self.stats["cache_hits"] += 1
                    self.last_flow_error = None
                    return {**data, "freshness": "CACHED", "cache_age_seconds": self._cache_age(data, now)}
                else:
                    stale_data = data
                    if (self._cache_age(stale_data, now) or 0) > 3600:
                        self._flow_cache.pop(cache_key, None)
                        stale_data = None
            if cache_key in self._flow_inflight:
                wait_for = self._flow_inflight[cache_key]
            else:
                owner_event = threading.Event()
                self._flow_inflight[cache_key] = owner_event

        if wait_for is not None:
            wait_for.wait(timeout=8.5)
            with self._lock:
                cached = self._flow_cache.get(cache_key)
            if cached and datetime.now() < cached[1]:
                self.stats["cache_hits"] += 1
                return {**cached[0], "freshness": "CACHED", "cache_age_seconds": self._cache_age(cached[0], datetime.now())}
            stale_data = cached[0] if cached else stale_data
            if stale_data and (self._cache_age(stale_data, datetime.now()) or 0) <= 3600:
                return {**stale_data, "freshness": "STALE", "cache_age_seconds": self._cache_age(stale_data, datetime.now())}
            self.last_flow_error = "A concurrent TomTom flow request did not populate the cache."
            return None

        try:
            if self._is_rate_limited():
                logger.debug("TomTom request suppressed by active circuit breaker.")
                self.last_flow_error = "TomTom rate limit is active; retry after the provider backoff period."
                if stale_data and (self._cache_age(stale_data, now) or 0) <= 3600:
                    return {**stale_data, "freshness": "STALE", "cache_age_seconds": self._cache_age(stale_data, now)}
                return None

            url = f"{self.base_url}/traffic/services/4/flowSegmentData/{style}/{zoom}/json"
            params = {
                "point": f"{lat},{lng}",
                "key": self.api_key,
            }

            self.stats["total_requests"] += 1
            self.last_flow_checked_at = now
            resp = self._request_with_retry(url, params, "traffic flow")
            self.flow_connectivity_status = "available" if resp.status_code == 200 else "unavailable"

            if resp.status_code == 200:
                raw = resp.json()
                segment = raw.get("flowSegmentData", {})
                current_speed = float(segment.get("currentSpeed", 0.0))
                free_flow_speed = float(segment.get("freeFlowSpeed", current_speed or 30.0))
                current_time = float(segment.get("currentTravelTime", 0.0))
                free_flow_time = float(segment.get("freeFlowTravelTime", current_time or 0.0))
                confidence = float(segment.get("confidence", 1.0))
                frc = segment.get("frc", "FRC2")
                road_closure = bool(segment.get("roadClosure", False))

                # Compute congestion and density
                speed_ratio = current_speed / free_flow_speed if free_flow_speed > 0 else 1.0
                delay_sec = max(0.0, current_time - free_flow_time)
                density = max(0.0, min(1.0, 1.0 - speed_ratio))

                if road_closure or speed_ratio < 0.30 or delay_sec > 180:
                    congestion = "HIGH"
                elif speed_ratio < 0.70 or delay_sec > 45:
                    congestion = "MEDIUM"
                else:
                    congestion = "LOW"

                coords_list = []
                for c in segment.get("coordinates", {}).get("coordinate", []):
                    if "latitude" in c and "longitude" in c:
                        coords_list.append([float(c["longitude"]), float(c["latitude"])])

                normalized = {
                    "source": "tomtom_traffic_flow",
                    "latitude": lat,
                    "longitude": lng,
                    "current_speed": current_speed,
                    "free_flow_speed": free_flow_speed,
                    "current_travel_time": current_time,
                    "free_flow_travel_time": free_flow_time,
                    "delay_seconds": delay_sec,
                    "speed_ratio": round(speed_ratio, 2),
                    "density": round(density, 3),
                    "congestion_level": congestion,
                    "confidence": round(confidence, 2),
                    "frc": frc,
                    "road_closure": road_closure,
                    "coordinates": coords_list,
                    "retrieved_at": now.isoformat(),
                }

                with self._lock:
                    for expired_key, (_, expiry) in list(self._flow_cache.items()):
                        if now >= expiry and expired_key != cache_key:
                            self._flow_cache.pop(expired_key, None)
                    self._flow_cache[cache_key] = (
                        normalized,
                        now + timedelta(seconds=self.cache_ttl),
                    )

                self.last_flow_error = None
                return normalized

            elif resp.status_code == 429:
                self._trigger_backoff(60)
                self.last_flow_error = "TomTom traffic flow returned HTTP 429 (rate limited)."
                return None
            elif resp.status_code in (401, 403):
                logger.error(
                    f"TomTom authentication/permission failure ({resp.status_code}) using key {self.masked_key}."
                )
                self.stats["errors"] += 1
                self.last_flow_error = f"TomTom authentication/permission failure (HTTP {resp.status_code})."
                return None
            else:
                logger.warning(
                    f"TomTom flowSegmentData query failed with status {resp.status_code}: {resp.text[:120]}"
                )
                self.stats["errors"] += 1
                self.last_flow_error = f"TomTom traffic flow returned HTTP {resp.status_code}."
                if stale_data and (self._cache_age(stale_data, now) or 0) <= 3600:
                    return {**stale_data, "freshness": "STALE", "cache_age_seconds": self._cache_age(stale_data, now)}
                return None

        except Exception as exc:
            self.flow_connectivity_status = "unavailable"
            self.last_flow_error = self._safe_request_error("traffic flow", exc)
            logger.warning(self.last_flow_error)
            self.stats["errors"] += 1
            if stale_data and (self._cache_age(stale_data, now) or 0) <= 3600:
                return {**stale_data, "freshness": "STALE", "cache_age_seconds": self._cache_age(stale_data, now)}
            return None
        finally:
            if owner_event is not None:
                with self._lock:
                    self._flow_inflight.pop(cache_key, None)
                    owner_event.set()

    # -------------------------------------------------------------------------
    # 2. Traffic Incidents Details (Bounding Box Corridor Query)
    # -------------------------------------------------------------------------
    def get_incident_details(
        self,
        min_lng: float,
        min_lat: float,
        max_lng: float,
        max_lat: float,
        language: str = "en-GB",
    ) -> list[dict[str, Any]]:
        """
        Retrieves real-time traffic incidents (accidents, stationary traffic, road works, etc.)
        within the specified bounding box.
        """
        if not self.is_configured:
            self.last_incident_error = "TOMTOM_API_KEY is not configured."
            return []

        # Round bbox to ~1km grid for cache reuse
        grid_min_lng = round(min_lng, 2)
        grid_min_lat = round(min_lat, 2)
        grid_max_lng = round(max_lng, 2)
        grid_max_lat = round(max_lat, 2)
        cache_key = f"{grid_min_lng}:{grid_min_lat}:{grid_max_lng}:{grid_max_lat}:{language}"

        now = datetime.now()
        wait_for: threading.Event | None = None
        owner_event: threading.Event | None = None
        with self._lock:
            if cache_key in self._incidents_cache:
                data, expire_at = self._incidents_cache[cache_key]
                if now < expire_at:
                    self.stats["cache_hits"] += 1
                    self.last_incident_error = None
                    return data
            if cache_key in self._incident_inflight:
                wait_for = self._incident_inflight[cache_key]
            else:
                owner_event = threading.Event()
                self._incident_inflight[cache_key] = owner_event

        if wait_for is not None:
            wait_for.wait(timeout=10.0)
            with self._lock:
                cached = self._incidents_cache.get(cache_key)
            if cached and datetime.now() < cached[1]:
                self.stats["cache_hits"] += 1
                return cached[0]
            self.last_incident_error = "A concurrent TomTom incident request did not populate the cache."
            return []

        try:
            if self._is_rate_limited():
                self.last_incident_error = "TomTom rate limit is active; retry after the provider backoff period."
                return []

            url = f"{self.base_url}/traffic/services/5/incidentDetails"
            fields = (
                "{incidents{type,geometry{type,coordinates},"
                "properties{id,iconCategory,magnitudeOfDelay,events{description,code},"
                "startTime,endTime,from,to,length,delay,roadNumbers}}}"
            )
            params = {
                "bbox": f"{min_lng},{min_lat},{max_lng},{max_lat}",
                "fields": fields,
                "language": language,
                "timeValidityFilter": "present",
                "key": self.api_key,
            }

            self.stats["total_requests"] += 1
            self.last_incident_checked_at = now
            resp = self._request_with_retry(url, params, "incidents")
            self.incident_connectivity_status = "available" if resp.status_code == 200 else "unavailable"

            if resp.status_code == 200:
                raw = resp.json()
                raw_incidents = raw.get("incidents", [])
                parsed_incidents: list[dict[str, Any]] = []

                for inc in raw_incidents:
                    props = inc.get("properties", {})
                    geom = inc.get("geometry", {})
                    icon_cat = int(props.get("iconCategory") or 0)
                    mag = int(props.get("magnitudeOfDelay") or 0)

                    events_list = props.get("events", [])
                    desc = (
                        events_list[0].get("description", "Traffic incident")
                        if events_list and isinstance(events_list, list) and events_list[0]
                        else TOMTOM_ICON_CATEGORIES.get(icon_cat, "Traffic incident")
                    )

                    delay_val = props.get("delay")
                    delay_sec = float(delay_val) if delay_val is not None else 0.0
                    length_val = props.get("length")
                    length_m = float(length_val) if length_val is not None else 0.0

                    coords = geom.get("coordinates", [])
                    centroid_lat = None
                    centroid_lng = None
                    if coords:
                        if geom.get("type") == "Point" and len(coords) >= 2:
                            centroid_lng, centroid_lat = float(coords[0]), float(coords[1])
                        elif geom.get("type") == "LineString" and len(coords) > 0:
                            mid_idx = len(coords) // 2
                            centroid_lng, centroid_lat = float(coords[mid_idx][0]), float(coords[mid_idx][1])

                    parsed_incidents.append({
                        "id": str(props.get("id") or f"INC_{icon_cat}_{len(parsed_incidents)}"),
                        "icon_category": icon_cat,
                        "category_name": TOMTOM_ICON_CATEGORIES.get(icon_cat, "Incident"),
                        "magnitude_of_delay": mag,
                        "magnitude_label": TOMTOM_DELAY_MAGNITUDE.get(mag, "Unknown"),
                        "description": desc,
                        "delay_seconds": delay_sec,
                        "length_meters": length_m,
                        "from_road": props.get("from"),
                        "to_road": props.get("to"),
                        "start_time": props.get("startTime"),
                        "end_time": props.get("endTime"),
                        "geometry": geom,
                        "centroid_lat": centroid_lat,
                        "centroid_lng": centroid_lng,
                        "source": "tomtom_traffic_incidents",
                    })

                with self._lock:
                    for expired_key, (_, expiry) in list(self._incidents_cache.items()):
                        if now >= expiry and expired_key != cache_key:
                            self._incidents_cache.pop(expired_key, None)
                    self._incidents_cache[cache_key] = (
                        parsed_incidents,
                        now + timedelta(seconds=self.incidents_ttl),
                    )

                self.last_incident_error = None
                return parsed_incidents

            elif resp.status_code == 429:
                self._trigger_backoff(60)
                self.last_incident_error = "TomTom incident service returned HTTP 429 (rate limited)."
                return []
            elif resp.status_code in (401, 403):
                self.last_incident_error = f"TomTom authentication/permission failure (HTTP {resp.status_code})."
                self.stats["errors"] += 1
                return []
            else:
                logger.warning(f"TomTom incidentDetails returned status {resp.status_code}")
                self.stats["errors"] += 1
                self.last_incident_error = f"TomTom incident service returned HTTP {resp.status_code}."
                return []

        except Exception as exc:
            self.incident_connectivity_status = "unavailable"
            self.last_incident_error = self._safe_request_error("incident", exc)
            logger.warning(self.last_incident_error)
            self.stats["errors"] += 1
            return []
        finally:
            if owner_event is not None:
                with self._lock:
                    self._incident_inflight.pop(cache_key, None)
                    owner_event.set()

    # -------------------------------------------------------------------------
    # 3. Raster and Vector Tiles (Traffic Flow & Incidents)
    # -------------------------------------------------------------------------
    def get_traffic_tile(
        self,
        layer: str,  # "flow" or "incidents"
        zoom: int,
        x: int,
        y: int,
        format: str = "png",
        style: str = "relative0",
    ) -> Optional[bytes]:
        """
        Retrieves a map tile for traffic flow or incidents with caching.
        Supports standard raster tiles (png) and Orbis vector tiles (pbf/mvt).
        """
        if not self.is_configured:
            return None

        cache_key = f"{layer}:{style}:{zoom}:{x}:{y}.{format}"
        now = datetime.now()
        with self._lock:
            if cache_key in self._tile_cache:
                data, expire_at = self._tile_cache[cache_key]
                if now < expire_at:
                    return data

        if self._is_rate_limited():
            return None

        # Determine endpoint based on layer and format
        if format == "pbf" or format == "mvt":
            # Orbis vector tile endpoints
            if layer == "flow":
                url = f"{self.base_url}/maps/orbis/traffic/flow/vector/tile/{zoom}/{x}/{y}"
                params = {"apiVersion": "2", "key": self.api_key}
            else:
                url = f"{self.base_url}/maps/orbis/traffic/tile/incidents/{zoom}/{x}/{y}.pbf"
                params = {"apiVersion": "1", "key": self.api_key}
        else:
            # Standard raster tile endpoints
            if layer == "flow":
                url = f"{self.base_url}/traffic/map/4/tile/flow/{style}/{zoom}/{x}/{y}.png"
            else:
                url = f"{self.base_url}/traffic/map/4/tile/incidents/s0/{zoom}/{x}/{y}.png"
            params = {"key": self.api_key}

        try:
            self.stats["total_requests"] += 1
            resp = self._request_with_retry(url, params, "map tile")

            if resp.status_code == 200:
                tile_bytes = resp.content
                with self._lock:
                    self._tile_cache[cache_key] = (
                        tile_bytes,
                        now + timedelta(seconds=self.cache_ttl),
                    )
                return tile_bytes
            elif resp.status_code == 429:
                self._trigger_backoff(60)
            return None
        except Exception as exc:
            logger.warning(f"TomTom tile request error: {exc}")
            return None

    # -------------------------------------------------------------------------
    # 4. Route Corridor Ingestion and Persistence to PostGIS
    # -------------------------------------------------------------------------
    def ingest_route_observations(
        self,
        route_coords: list[list[float]],  # [[lng, lat], ...] from GeoJSON
        db: Session,
        max_sample_points: int = 4,
    ) -> dict[str, Any]:
        """
        Extracts representative sampling waypoints along the route geometry,
        queries TomTom for flow data and incidents, and persists them into
        PostgreSQL / PostGIS with full provenance tracking.
        """
        if not self.is_configured or not route_coords or len(route_coords) < 2:
            return {"flow_count": 0, "incident_count": 0, "incidents": []}

        # 1. Compute bounding box
        lngs = [c[0] for c in route_coords]
        lats = [c[1] for c in route_coords]
        min_lng, max_lng = min(lngs) - 0.015, max(lngs) + 0.015
        min_lat, max_lat = min(lats) - 0.015, max(lats) + 0.015

        # 2. Pick representative sample points along the route
        total_pts = len(route_coords)
        sample_indices = []
        if total_pts <= max_sample_points:
            sample_indices = list(range(total_pts))
        else:
            step = total_pts / (max_sample_points + 1)
            sample_indices = [int(step * (i + 1)) for i in range(max_sample_points)]

        flow_observations: list[dict[str, Any]] = []
        now = datetime.now()

        from concurrent.futures import ThreadPoolExecutor

        def _fetch_point(idx):
            pt = route_coords[idx]
            return self.get_flow_segment_data(pt[1], pt[0])

        with ThreadPoolExecutor(max_workers=min(len(sample_indices) or 1, 5)) as executor:
            raw_flow_results = list(executor.map(_fetch_point, sample_indices))
        flow_observations = [f for f in raw_flow_results if f is not None]
        persistable_flow = [f for f in flow_observations if f.get("freshness", "FRESH") == "FRESH"]

        # 3. Query incident details for the corridor bbox
        corridor_incidents = self.get_incident_details(min_lng, min_lat, max_lng, max_lat)

        # 4. Persist flow observations to PostGIS (traffic_stream_events)
        ingested_events: list[TrafficStreamEvent] = []
        for flow in persistable_flow:
            f_lat = flow["latitude"]
            f_lng = flow["longitude"]

            # Deduplication: check if an event exists within 150m from tomtom in last 5 minutes
            recent_exists = db.execute(
                text("""
                    SELECT id FROM traffic_stream_events
                    WHERE ST_DWithin(
                        location::geography,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                        150
                    )
                    AND timestamp > :cutoff
                    LIMIT 1
                """),
                {"lng": f_lng, "lat": f_lat, "cutoff": now - timedelta(seconds=300)},
            ).first()

            if not recent_exists:
                # Estimate vehicle count: free flow carries ~10-14 vehicles/500m; high congestion ~30-45
                est_vehicles = int(12 + (30 * flow["density"]))

                event = TrafficStreamEvent(
                    total_vehicles=est_vehicles,
                    average_speed=flow["current_speed"],
                    density=flow["density"],
                    congestion_level=flow["congestion_level"],
                    vehicle_types={"car": int(est_vehicles * 0.6), "two_wheeler": int(est_vehicles * 0.3), "bus": int(est_vehicles * 0.1)},
                    lane_counts={"delay_seconds": flow["delay_seconds"]},
                    direction_counts={"current_travel_time": flow["current_travel_time"], "free_flow_travel_time": flow["free_flow_travel_time"]},
                    events=[
                        {
                            "source": "tomtom_traffic_flow",
                            "provider": "TomTom",
                            "frc": flow["frc"],
                            "free_flow_speed": flow["free_flow_speed"],
                            "current_speed": flow["current_speed"],
                            "delay_seconds": flow["delay_seconds"],
                            "confidence": flow["confidence"],
                            "road_closure": flow["road_closure"],
                            "ingested_at": now.isoformat(),
                        }
                    ],
                    latitude=f_lat,
                    longitude=f_lng,
                    location=WKTElement(f"POINT({f_lng} {f_lat})", srid=POSTGIS_SRID),
                    timestamp=now,
                )
                db.add(event)
                ingested_events.append(event)

        # 5. Persist relevant corridor incidents to PostGIS
        for inc in corridor_incidents:
            c_lat = inc.get("centroid_lat")
            c_lng = inc.get("centroid_lng")
            if c_lat is not None and c_lng is not None:
                inc_exists = db.execute(
                    text("""
                        SELECT id FROM traffic_stream_events
                        WHERE ST_DWithin(
                            location::geography,
                            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                            100
                        )
                        AND timestamp > :cutoff
                        LIMIT 1
                    """),
                    {"lng": c_lng, "lat": c_lat, "cutoff": now - timedelta(seconds=600)},
                ).first()

                if not inc_exists:
                    inc_event = TrafficStreamEvent(
                        total_vehicles=5,
                        average_speed=0.0,
                        density=1.0 if inc["delay_seconds"] > 0 else 0.5,
                        congestion_level="HIGH" if inc["magnitude_of_delay"] >= 2 else "MEDIUM",
                        vehicle_types={},
                        lane_counts={"delay_seconds": inc["delay_seconds"]},
                        direction_counts={"length_meters": inc["length_meters"]},
                        events=[
                            {
                                "source": "tomtom_traffic_incidents",
                                "provider": "TomTom",
                                "incident_id": inc["id"],
                                "icon_category": inc["icon_category"],
                                "category_name": inc["category_name"],
                                "description": inc["description"],
                                "delay_seconds": inc["delay_seconds"],
                                "length_meters": inc["length_meters"],
                                "from_road": inc.get("from_road"),
                                "to_road": inc.get("to_road"),
                                "start_time": inc.get("start_time"),
                                "end_time": inc.get("end_time"),
                                "geometry": inc.get("geometry"),
                                "ingested_at": now.isoformat(),
                            }
                        ],
                        latitude=c_lat,
                        longitude=c_lng,
                        location=WKTElement(f"POINT({c_lng} {c_lat})", srid=POSTGIS_SRID),
                        timestamp=now,
                    )
                    db.add(inc_event)
                    ingested_events.append(inc_event)

        if ingested_events:
            try:
                db.commit()
                from backend.app.services.alert_service import process_alert_event
                for event in ingested_events:
                    db.refresh(event)
                    metadata = event.events[0] if isinstance(event.events, list) and event.events else {}
                    event_source_id = metadata.get("incident_id") or f"tomtom-flow:{event.id}"
                    process_alert_event(db, {
                        "source": metadata.get("source", "tomtom_traffic_flow"),
                        "source_event_id": event_source_id,
                        "timestamp": event.timestamp,
                        "intersection_id": event.intersection_id,
                        "latitude": event.latitude,
                        "longitude": event.longitude,
                        "total_vehicles": event.total_vehicles,
                        "average_speed": event.average_speed,
                        "free_flow_speed": metadata.get("free_flow_speed"),
                        "density": event.density,
                        "congestion_level": event.congestion_level,
                        "delay_seconds": metadata.get("delay_seconds"),
                        "road_closure": metadata.get("road_closure", False),
                        "events": event.events or [],
                    })
            except Exception as commit_err:
                db.rollback()
                logger.warning("TomTom corridor persisted; alert evaluation or follow-up failed: %s", commit_err)

        return {
            "flow_count": len(flow_observations),
            "incident_count": len(corridor_incidents),
            "incidents": corridor_incidents,
            "flow_observations": flow_observations,
        }

    # -------------------------------------------------------------------------
    # 5. City-Wide / Intersections Live Telemetry Retrieval
    # -------------------------------------------------------------------------
    def get_chennai_live_snapshot(self, db: Session) -> dict[str, Any]:
        """
        Fetches live TomTom traffic flow for monitored arterial junctions
        and active incidents across Chennai. Returns a comprehensive snapshot.
        """
        now = datetime.now()
        # Fetch registered intersections from database
        intersections = db.execute(
            text("SELECT intersection_id, name, latitude, longitude FROM intersections LIMIT 6")
        ).fetchall()

        junction_metrics: list[dict[str, Any]] = []
        from concurrent.futures import ThreadPoolExecutor

        def _fetch_flow(row):
            flow = self.get_flow_segment_data(float(row.latitude), float(row.longitude))
            if flow:
                f_copy = dict(flow)
                f_copy["intersection_id"] = row.intersection_id
                f_copy["name"] = row.name
                return f_copy
            return None

        with ThreadPoolExecutor(max_workers=min(len(intersections) or 1, 6)) as executor:
            flow_results = list(executor.map(_fetch_flow, intersections))
        junction_metrics = [f for f in flow_results if f is not None]

        # Chennai Greater Metro Bounding Box
        incidents = self.get_incident_details(
            min_lng=80.12,
            min_lat=12.94,
            max_lng=80.32,
            max_lat=13.18,
        )

        avg_speed = (
            round(sum(j["current_speed"] for j in junction_metrics) / len(junction_metrics), 1)
            if junction_metrics
            else 0.0
        )
        avg_density = (
            round(sum(j["density"] for j in junction_metrics) / len(junction_metrics), 3)
            if junction_metrics
            else 0.0
        )
        total_delay = sum(j.get("delay_seconds", 0.0) for j in junction_metrics)
        provider_errors = [
            error
            for error in (self.last_flow_error, self.last_incident_error)
            if error
        ]
        provider_error = "; ".join(dict.fromkeys(provider_errors)) or None

        return {
            "status": "ACTIVE" if junction_metrics else "UNAVAILABLE",
            "provider": "TomTom Traffic API",
            "timestamp": now.isoformat(),
            "intersections_monitored": len(junction_metrics),
            "average_speed": avg_speed,
            "average_density": avg_density,
            "total_delay_seconds": round(total_delay, 1),
            "active_incidents_count": len(incidents),
            "junctions": junction_metrics,
            "incidents": incidents[:10],  # top 10 most relevant incidents
            "provider_error": provider_error,
            "message": (
                f"Live telemetry from TomTom across {len(junction_metrics)} arterial hubs in Chennai."
                if not provider_error
                else f"TomTom live traffic request failed: {provider_error}"
            ),
        }


# Singleton service instance
tomtom_traffic_service = TomTomTrafficService()
