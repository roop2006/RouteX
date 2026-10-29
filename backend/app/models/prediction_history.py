from datetime import datetime
from sqlalchemy import (
    Integer,
    String,
    Float,
    DateTime,
    JSON,
    Index
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column
)

from ..core.database import Base


class PredictionHistory(Base):
    __tablename__ = "prediction_history"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    prediction_timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

    model_name: Mapped[str] = mapped_column(
        String(100),
        index=True
    )

    model_version: Mapped[str] = mapped_column(
        String(50),
        default="v1.0.0"
    )

    forecast_target: Mapped[str] = mapped_column(
        String(100),
        default="traffic_volume"
    )

    forecast_horizon: Mapped[str] = mapped_column(
        String(50),
        default="1_step"
    )

    predicted_value: Mapped[float] = mapped_column(
        Float
    )

    predicted_congestion: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    prediction_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    actual_value: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    actual_congestion: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    actual_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    evaluation_status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        index=True
    )

    absolute_error: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    squared_error: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    intersection_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True
    )

    input_features: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )
