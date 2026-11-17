"""
Live Traffic Service for RouteX.
Handles live traffic ingestion, provider integration, multi-tier caching (Redis + PostgreSQL),
and robust fallback to prevent infinite loading when streaming workers are idle.
"""
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Optional

import redis
from geoalchemy2.elements import WKTElement
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal
from backend.app.core.geo_config import (
    DEFAULT_CAMERA_LATITUDE,
    DEFAULT_CAMERA_LONGITUDE,
    DEFAULT_INTERSECTION_ID,
    POSTGIS_SRID,
)
from backend.app.models.traffic_stream_event import TrafficStreamEvent
from vision.streaming.redis_client import TrafficRedis

logger = logging.getLogger(__name__)

# Configurable provider settings (read from environment, never hardcoded)
TRAFFIC_API_PROVIDER = os.getenv("TRAFFIC_API_PROVIDER", "routex_stream")
TRAFFIC_API_KEY = os.getenv("TRAFFIC_API_KEY", "")


class LiveTrafficService:
    def __init__(self):
        self.redis_client = TrafficRedis()

    def get_latest_live_traffic(self, db: Optional[Session] = None) -> dict[str, Any]:
        """
        Retrieves the latest available live traffic telemetry with multi-tier fallback:
        1. Redis active stream buffer ('routex:traffic:latest').
        2. PostgreSQL latest TrafficStreamEvent telemetry record.
        3. Graceful empty telemetry status (HTTP 200 with clear 'UNAVAILABLE' state)
           to prevent frontend infinite loading or unhandled 404/503 retry storms.
        """
        # Tier 1: Check Redis active stream
        try:
            redis_data = self.redis_client.get_latest()
            if redis_data and isinstance(redis_data, dict):
                redis_data.setdefault("source", "redis_live_stream")
                redis_data.setdefault("freshness", "FRESH")
                redis_data.setdefault("status", "ACTIVE" if redis_data["freshness"] == "FRESH" else "CACHED_STREAM")
                return redis_data
        except (redis.exceptions.RedisError, ConnectionError, TimeoutError, Exception) as err:
            logger.debug(f"Redis live stream read skipped / unavailable: {err}")

        # Tier 2: Check TomTom Live Traffic API (External Live Data Provider)
        tomtom_provider_error: Optional[str] = None
        try:
            from backend.app.services.tomtom_traffic_service import tomtom_traffic_service
            if tomtom_traffic_service.is_configured:
                tomtom_flow = tomtom_traffic_service.get_flow_segment_data(
                    DEFAULT_CAMERA_LATITUDE, DEFAULT_CAMERA_LONGITUDE
                )
                if tomtom_flow:
                    est_veh = None  # Provider has no vehicle count or class distribution.
                    tt_payload = {
                        "status": "ACTIVE" if tomtom_flow.get("freshness", "FRESH") == "FRESH" else "CACHED_STREAM",
                        "source": "tomtom_traffic_flow",
                        "provider": "TomTom Traffic API",
                        "timestamp": tomtom_flow.get("retrieved_at", datetime.now(timezone.utc).replace(tzinfo=None).isoformat()),
                        "intersection_id": DEFAULT_INTERSECTION_ID,
                        "latitude": DEFAULT_CAMERA_LATITUDE,
                        "longitude": DEFAULT_CAMERA_LONGITUDE,
                        "total_vehicles": est_veh,
                        "average_speed": tomtom_flow["current_speed"],
                        "free_flow_speed": tomtom_flow["free_flow_speed"],
                        "density": tomtom_flow["density"],
                        "congestion_level": tomtom_flow["congestion_level"],
                        "delay_seconds": tomtom_flow["delay_seconds"],
                        "confidence": tomtom_flow["confidence"],
                        "frc": tomtom_flow["frc"],
                        "road_closure": tomtom_flow["road_closure"],
                        "vehicle_types": {},
                        "lane_counts": {"delay_seconds": tomtom_flow["delay_seconds"]},
                        "direction_counts": {
                            "current_travel_time": tomtom_flow["current_travel_time"],
                            "free_flow_travel_time": tomtom_flow["free_flow_travel_time"],
                        },
                        "events": [tomtom_flow],
                        "freshness": tomtom_flow.get("freshness", "FRESH"),
                        "cache_age_seconds": tomtom_flow.get("cache_age_seconds", 0),
                        "provider_error": tomtom_traffic_service.last_flow_error,
                        "message": "Real-time traffic flow retrieved from TomTom Traffic API.",
                    }
                    if tt_payload["freshness"] != "FRESH":
                        tt_payload["status"] = "CACHED_STREAM"
                        tt_payload["message"] = (
                            "TomTom is unavailable; serving a stale cached traffic flow snapshot."
                            if tt_payload["freshness"] == "STALE"
                            else "Serving a recently cached TomTom traffic flow snapshot."
                        )
                    else:
                        owns_alert_session = db is None
                        alert_db = SessionLocal() if owns_alert_session else db
                        try:
                            from backend.app.services.alert_service import process_alert_event
                            process_alert_event(alert_db, {
                                "source": "tomtom_traffic_flow",
                                "source_event_id": f"tomtom-flow-live:{DEFAULT_INTERSECTION_ID}:{tt_payload['timestamp']}",
                                "timestamp": tt_payload["timestamp"],
                                "intersection_id": DEFAULT_INTERSECTION_ID,
                                "latitude": DEFAULT_CAMERA_LATITUDE,
                                "longitude": DEFAULT_CAMERA_LONGITUDE,
                                "total_vehicles": est_veh,
                                "average_speed": tomtom_flow["current_speed"],
                                "free_flow_speed": tomtom_flow["free_flow_speed"],
                                "density": tomtom_flow["density"],
                                "congestion_level": tomtom_flow["congestion_level"],
                                "delay_seconds": tomtom_flow["delay_seconds"],
                                "road_closure": tomtom_flow["road_closure"],
                                "events": [tomtom_flow],
                            })
                        except Exception as alert_error:
                            logger.warning("Fresh TomTom flow retrieved; alert evaluation skipped: %s", alert_error)
                        finally:
                            if owns_alert_session:
                                alert_db.close()
                    return tt_payload
                tomtom_provider_error = tomtom_traffic_service.last_flow_error
            else:
                tomtom_provider_error = "TOMTOM_API_KEY is not configured."
        except Exception as tt_err:
            logger.debug(f"TomTom live traffic retrieval skipped: {tt_err}")
            tomtom_provider_error = f"TomTom live traffic retrieval failed: {tt_err}"

        # Tier 3: Fallback to latest database stream observation
        owns_session = False
        if db is None:
            db = SessionLocal()
            owns_session = True

        try:
            latest_db_event = (
                db.query(TrafficStreamEvent)
                .filter(TrafficStreamEvent.timestamp.isnot(None))
                .filter(text("COALESCE(events::jsonb->0->>'source', '') NOT IN ('historical_chennai_arterial_benchmark', 'tomtom_traffic_incidents')"))
                .order_by(TrafficStreamEvent.timestamp.desc(), TrafficStreamEvent.id.desc())
                .first()
            )

            if latest_db_event:
                ts_iso = (
                    latest_db_event.timestamp.isoformat()
                    if latest_db_event.timestamp
                    else datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
                )
                source_meta = "database_stream_telemetry"
                if isinstance(latest_db_event.events, dict) and latest_db_event.events.get("source"):
                    source_meta = latest_db_event.events["source"]
                elif isinstance(latest_db_event.events, list) and latest_db_event.events:
                    first_event = latest_db_event.events[0]
                    if isinstance(first_event, dict) and first_event.get("source"):
                        source_meta = first_event["source"]

                event_time = latest_db_event.timestamp
                age_seconds = max(0, int((datetime.now(timezone.utc).replace(tzinfo=None) - event_time).total_seconds())) if event_time else None
                freshness = "UNAVAILABLE" if age_seconds is None else "FRESH" if age_seconds <= 30 else "RECENT" if age_seconds <= 300 else "HISTORICAL"

                return {
                    "status": "CACHED_STREAM",
                    "source": source_meta,
                    "timestamp": ts_iso,
                    "intersection_id": latest_db_event.intersection_id or DEFAULT_INTERSECTION_ID,
                    "latitude": latest_db_event.latitude if latest_db_event.latitude is not None else DEFAULT_CAMERA_LATITUDE,
                    "longitude": latest_db_event.longitude if latest_db_event.longitude is not None else DEFAULT_CAMERA_LONGITUDE,
                    "total_vehicles": None if source_meta == "tomtom_traffic_flow" else latest_db_event.total_vehicles,
                    "average_speed": round(float(latest_db_event.average_speed or 0.0), 1),
                    "density": round(float(latest_db_event.density or 0.0), 3),
                    "congestion_level": latest_db_event.congestion_level or "LOW",
                    "vehicle_types": {} if source_meta == "tomtom_traffic_flow" else latest_db_event.vehicle_types or {},
                    "lane_counts": latest_db_event.lane_counts or {},
                    "direction_counts": latest_db_event.direction_counts or {},
                    "events": latest_db_event.events or [],
                    "freshness": freshness,
                    "cache_age_seconds": age_seconds,
                    "message": "Telemetry snapshot retrieved from RouteX historical stream storage.",
                    "provider_error": tomtom_provider_error,
                }
        except Exception as exc:
            logger.warning(f"Database fallback query failed: {exc}")
        finally:
            if owns_session:
                db.close()

        # Tier 3: Clean unavailable payload (replaces hard 404 to stop infinite loading)
        now_iso = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        return {
            "status": "UNAVAILABLE",
            "source": "none",
            "timestamp": now_iso,
            "intersection_id": DEFAULT_INTERSECTION_ID,
            "latitude": DEFAULT_CAMERA_LATITUDE,
            "longitude": DEFAULT_CAMERA_LONGITUDE,
            "total_vehicles": None,
            "average_speed": None,
            "density": None,
            "freshness": "UNAVAILABLE",
            "congestion_level": "UNKNOWN",
            "vehicle_types": {},
            "lane_counts": {},
            "direction_counts": {},
            "events": [],
            "message": "No active live traffic stream in Redis buffer or database telemetry.",
            "provider_error": tomtom_provider_error,
        }

    def ingest_traffic_snapshot(
        self,
        snapshot: dict[str, Any],
        db: Optional[Session] = None,
        publish_to_redis: bool = True,
    ) -> TrafficStreamEvent:
        """
        Validates, normalizes, and stores an incoming live traffic observation
        into PostgreSQL/PostGIS and optionally publishes to Redis buffer.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        ts = snapshot.get("timestamp")
        if isinstance(ts, str):
            try:
                event_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                event_time = now
        elif isinstance(ts, datetime):
            event_time = ts
        else:
            event_time = now

        if event_time.tzinfo is not None:
            event_time = event_time.astimezone(timezone.utc).replace(tzinfo=None)

        lat = snapshot.get("latitude", DEFAULT_CAMERA_LATITUDE)
        lng = snapshot.get("longitude", DEFAULT_CAMERA_LONGITUDE)
        intersection_id = snapshot.get("intersection_id", DEFAULT_INTERSECTION_ID)

        # Coordinate bounds validation
        if lat is not None and not (-90.0 <= lat <= 90.0):
            raise ValueError(f"Invalid latitude: {lat}")
        if lng is not None and not (-180.0 <= lng <= 180.0):
            raise ValueError(f"Invalid longitude: {lng}")

        # PostGIS Point representation
        location = None
        if lat is not None and lng is not None:
            location = WKTElement(f"POINT({lng} {lat})", srid=POSTGIS_SRID)

        source_info = snapshot.get("source", "live_traffic_api")
        raw_events = snapshot.get("events")
        if isinstance(raw_events, list):
            events_data = raw_events
        elif isinstance(raw_events, dict):
            events_data = [raw_events]
        else:
            events_data = [{"source": source_info, "ingested_at": now.isoformat()}]

        owns_session = False
        if db is None:
            db = SessionLocal()
            owns_session = True

        try:
            db_event = TrafficStreamEvent(
                total_vehicles=int(snapshot.get("total_vehicles", 0)),
                vehicle_types=snapshot.get("vehicle_types", {}),
                lane_counts=snapshot.get("lane_counts", {}),
                direction_counts=snapshot.get("direction_counts", {}),
                average_speed=float(snapshot.get("average_speed", 0.0)),
                density=float(snapshot.get("density", 0.0)),
                congestion_level=str(snapshot.get("congestion_level", "LOW")).upper(),
                events=events_data,
                intersection_id=intersection_id,
                latitude=lat,
                longitude=lng,
                location=location,
                timestamp=event_time,
            )

            db.add(db_event)
            db.commit()
            db.refresh(db_event)

            try:
                from backend.app.services.alert_service import process_alert_event
                process_alert_event(
                    db,
                    {
                        "source": source_info,
                        "source_event_id": snapshot.get("source_event_id") or f"traffic-stream:{db_event.id}",
                        "timestamp": event_time,
                        "intersection_id": intersection_id,
                        "latitude": lat,
                        "longitude": lng,
                        "total_vehicles": db_event.total_vehicles,
                        "average_speed": db_event.average_speed,
                        "free_flow_speed": snapshot.get("free_flow_speed"),
                        "density": db_event.density,
                        "congestion_level": db_event.congestion_level,
                        "delay_seconds": snapshot.get("delay_seconds"),
                        "road_closure": snapshot.get("road_closure", False),
                        "predicted_congestion": snapshot.get("predicted_congestion"),
                        "anomaly_detected": snapshot.get("anomaly_detected", False),
                        "events": events_data,
                    },
                )
            except Exception as alert_error:
                logger.warning("Traffic snapshot stored; alert generation skipped: %s", alert_error)

            # Publish to Redis buffer if enabled
            if publish_to_redis:
                try:
                    payload = {
                        "timestamp": event_time.isoformat(),
                        "intersection_id": intersection_id,
                        "latitude": lat,
                        "longitude": lng,
                        "total_vehicles": db_event.total_vehicles,
                        "average_speed": db_event.average_speed,
                        "density": db_event.density,
                        "congestion_level": db_event.congestion_level,
                        "vehicle_types": db_event.vehicle_types,
                        "lane_counts": db_event.lane_counts,
                        "direction_counts": db_event.direction_counts,
                        "events": db_event.events,
                        "source": source_info,
                        "status": "ACTIVE",
                    }
                    self.redis_client.set_latest(payload)
                except Exception as r_err:
                    logger.debug(f"Could not update Redis buffer: {r_err}")

            return db_event
        except Exception:
            db.rollback()
            raise
        finally:
            if owns_session:
                db.close()


# Singleton instance
live_traffic_service = LiveTrafficService()
