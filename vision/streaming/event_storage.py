from geoalchemy2.elements import WKTElement

from backend.app.core.database import SessionLocal
from backend.app.core.geo_config import (
    DEFAULT_INTERSECTION_ID,
    DEFAULT_CAMERA_LATITUDE,
    DEFAULT_CAMERA_LONGITUDE,
    POSTGIS_SRID,
)
from backend.app.models.traffic_stream_event import (
    TrafficStreamEvent
)


def save_traffic_event(data):

    db = SessionLocal()

    try:

        latitude = data.get("latitude", DEFAULT_CAMERA_LATITUDE)
        longitude = data.get("longitude", DEFAULT_CAMERA_LONGITUDE)
        intersection_id = data.get("intersection_id", DEFAULT_INTERSECTION_ID)

        location = None
        if latitude is not None and longitude is not None:
            location = WKTElement(
                f"POINT({longitude} {latitude})",
                srid=POSTGIS_SRID
            )

        event = TrafficStreamEvent(

            total_vehicles=data.get(
                "total_vehicles",
                0
            ),

            vehicle_types=data.get(
                "vehicle_types",
                {}
            ),

            lane_counts=data.get(
                "lane_counts",
                {}
            ),

            direction_counts=data.get(
                "direction_counts",
                {}
            ),

            average_speed=data.get(
                "average_speed",
                0.0
            ),

            density=data.get(
                "density",
                0.0
            ),

            congestion_level=data.get(
                "congestion_level",
                "UNKNOWN"
            ),

            events=data.get(
                "events",
                []
            ),

            intersection_id=intersection_id,

            latitude=latitude,

            longitude=longitude,

            location=location,
        )

        db.add(event)

        db.commit()

        print(
            f"PostgreSQL event saved | "
            f"vehicles={event.total_vehicles} | "
            f"intersection={intersection_id} | "
            f"point=POINT({longitude} {latitude})"
        )

    except Exception as error:

        db.rollback()

        print(
            "PostgreSQL error:",
            error
        )

        raise

    finally:

        db.close()