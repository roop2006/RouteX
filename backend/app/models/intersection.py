from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from geoalchemy2 import Geometry

from ..core.database import Base


class Intersection(Base):

    __tablename__ = "intersections"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    intersection_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(150)
    )

    latitude: Mapped[float]

    longitude: Mapped[float]

    location = mapped_column(
        Geometry(
            geometry_type="POINT",
            srid=4326,
            spatial_index=True
        )
    )