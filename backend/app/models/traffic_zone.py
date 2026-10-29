from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from geoalchemy2 import Geometry


from ..core.database import Base


class TrafficZone(Base):

    __tablename__ = "traffic_zones"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    zone_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(150)
    )

    zone_type: Mapped[str] = mapped_column(
        String(50)
    )

    geometry = mapped_column(
        Geometry(
            geometry_type="POLYGON",
            srid=4326,
            spatial_index=True
        )
    )