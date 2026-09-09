from datetime import datetime

from sqlalchemy import (
    String,
    Integer,
    Float,
    DateTime,
    Index
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class TrafficEvent(Base):
    __tablename__ = "traffic_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    vehicle_type: Mapped[str] = mapped_column(
        String(50),
        index=True
    )

    vehicle_count: Mapped[int] = mapped_column(Integer)

    latitude: Mapped[float] = mapped_column(Float)

    longitude: Mapped[float] = mapped_column(Float)

    congestion_level: Mapped[str] = mapped_column(
        String(20),
        index=True
    )

    detected_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )