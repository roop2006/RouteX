from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models.traffic_event import TrafficEvent
from ..schemas.traffic_event import TrafficEventCreate


def create_traffic_event(
    db: Session,
    event: TrafficEventCreate
):
    try:
        db_event = TrafficEvent(**event.model_dump())

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
    vehicle_type: str | None = None,
    congestion_level: str | None = None
):
    query = db.query(TrafficEvent)

    if vehicle_type:
        query = query.filter(
            TrafficEvent.vehicle_type == vehicle_type
        )

    if congestion_level:
        query = query.filter(
            TrafficEvent.congestion_level == congestion_level
        )

    return (
        query
        .offset(skip)
        .limit(limit)
        .all()
    )