import logging
from datetime import datetime, timezone

from geoalchemy2.elements import WKTElement

from backend.app.core.database import SessionLocal
from backend.app.core.geo_config import POSTGIS_SRID
from backend.app.models.traffic_stream_event import TrafficStreamEvent
from backend.app.schemas.alerts import AlertEventInput
from backend.app.services.alert_service import process_alert_event

logger = logging.getLogger("routex.kafka_storage")


def save_traffic_event(data: dict, source_event_id: str | None = None):
    """Validate and persist a Kafka traffic event, then evaluate alert rules."""
    validated = AlertEventInput.model_validate(data)
    normalized = validated.model_dump(exclude_none=True)
    if source_event_id:
        normalized["source_event_id"] = source_event_id

    db = SessionLocal()
    try:
        latitude = normalized.get("latitude")
        longitude = normalized.get("longitude")
        location = None
        if latitude is not None and longitude is not None:
            location = WKTElement(f"POINT({longitude} {latitude})", srid=POSTGIS_SRID)

        event = TrafficStreamEvent(
            total_vehicles=normalized.get("total_vehicles", 0),
            vehicle_types=normalized.get("vehicle_types", {}),
            lane_counts=normalized.get("lane_counts", {}),
            direction_counts=normalized.get("direction_counts", {}),
            average_speed=normalized.get("average_speed", 0.0),
            density=normalized.get("density", 0.0),
            congestion_level=normalized.get("congestion_level", "UNKNOWN"),
            events=normalized.get("events", []),
            intersection_id=normalized.get("intersection_id"),
            latitude=latitude,
            longitude=longitude,
            location=location,
            timestamp=normalized.get("timestamp") or datetime.now(timezone.utc),
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        alert_payload = dict(normalized)
        if alert_payload["source"].lower().startswith("cam_") and alert_payload.get("events"):
            alert_payload["anomaly_detected"] = True
        process_alert_event(db, alert_payload, source_event_id=source_event_id)
        logger.info(
            "Kafka traffic event persisted: event_id=%s source=%s",
            event.id,
            normalized["source"],
        )
        return event
    except Exception:
        db.rollback()
        logger.exception("Kafka traffic event processing failed")
        raise
    finally:
        db.close()
