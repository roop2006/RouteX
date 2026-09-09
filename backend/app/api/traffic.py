from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..schemas.traffic_event import (
    TrafficEventCreate,
    TrafficEventResponse,
)
from ..services.traffic_service import (
    create_traffic_event,
    get_traffic_events,
)


router = APIRouter(
    prefix="/traffic-events",
    tags=["Traffic Events"]
)


@router.post(
    "/",
    response_model=TrafficEventResponse
)
def create_event(
    event: TrafficEventCreate,
    db: Session = Depends(get_db)
):
    return create_traffic_event(db, event)


@router.get(
    "/",
    response_model=list[TrafficEventResponse]
)
def get_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    vehicle_type: str | None = None,
    congestion_level: str | None = None,
    db: Session = Depends(get_db)
):
    return get_traffic_events(
        db=db,
        skip=skip,
        limit=limit,
        vehicle_type=vehicle_type,
        congestion_level=congestion_level
    )