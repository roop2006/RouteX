from datetime import timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models.traffic_stream_event import TrafficStreamEvent
from ..schemas.traffic_event import TrafficEventCreate


def create_traffic_event(
    db: Session,
    event: TrafficEventCreate
):
    try:
        db_event = TrafficStreamEvent(
            total_vehicles=event.total_vehicles,
            vehicle_types=event.vehicle_types,
            lane_counts=event.lane_counts,
            direction_counts=event.direction_counts,
            average_speed=event.average_speed,
            density=event.density,
            congestion_level=event.congestion_level,
            events=event.events
        )

        db.add(db_event)
        db.commit()
        db.refresh(db_event)

        try:
            from backend.app.services.alert_service import process_alert_event
            first_metadata = next((item for item in (event.events or []) if isinstance(item, dict)), {})
            process_alert_event(db, {
                **event.model_dump(),
                "source": first_metadata.get("source", "traffic_events_api"),
                "source_event_id": first_metadata.get("id") or first_metadata.get("source_event_id")
                    or f"traffic-event:{db_event.id}",
                "timestamp": first_metadata.get("timestamp") or db_event.timestamp.replace(tzinfo=timezone.utc),
            })
        except Exception:
            # The existing traffic event remains committed if alerting is unavailable.
            import logging
            logging.getLogger(__name__).exception("Traffic event stored; alert generation failed")

        return db_event

    except SQLAlchemyError:
        db.rollback()
        raise


def get_traffic_events(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    congestion_level: str | None = None
):
    query = db.query(TrafficStreamEvent)

    if congestion_level:
        query = query.filter(
            TrafficStreamEvent.congestion_level == congestion_level
        )

    return (
        query
        .order_by(TrafficStreamEvent.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
