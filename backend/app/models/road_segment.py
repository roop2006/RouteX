from sqlalchemy import String, Float
from sqlalchemy.orm import Mapped, mapped_column

from geoalchemy2 import Geometry

from ..core.database import Base


class RoadSegment(Base):

    __tablename__ = "road_segments"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    road_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True
    )

    road_name: Mapped[str] = mapped_column(
        String(150)
    )

    speed_limit: Mapped[float] = mapped_column(
        Float
    )

    lanes: Mapped[int] = mapped_column()

    geometry = mapped_column(
        Geometry(
            geometry_type="LINESTRING",
            srid=4326,
            spatial_index=True
        )
    )