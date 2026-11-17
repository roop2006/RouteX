from datetime import datetime

from sqlalchemy import (
    Integer,
    String,
    Float,
    DateTime,
    JSON
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column
)

from geoalchemy2 import Geometry

from ..core.database import Base


class TrafficStreamEvent(Base):

    __tablename__ = "traffic_stream_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    source_event_id: Mapped[str | None] = mapped_column(String(220), nullable=True, unique=True)

    total_vehicles: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    vehicle_types: Mapped[dict] = mapped_column(
        JSON
    )

    lane_counts: Mapped[dict] = mapped_column(
        JSON
    )

    direction_counts: Mapped[dict] = mapped_column(
        JSON
    )

    average_speed: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    density: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    congestion_level: Mapped[str] = mapped_column(
        String(20)
    )

    events: Mapped[list] = mapped_column(
        JSON
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    intersection_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    location = mapped_column(
        Geometry(
            geometry_type="POINT",
            srid=4326,
            spatial_index=True
        ),
        nullable=True
    )
