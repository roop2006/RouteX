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