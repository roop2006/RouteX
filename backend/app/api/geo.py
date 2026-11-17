from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.database import get_db


router = APIRouter(
    prefix="/geo",
    tags=["Geospatial"]
)


@router.get("/nearby-events")
def nearby_events(
    latitude: float,
    longitude: float,
    radius_meters: float = 500,
    db: Session = Depends(get_db)
):

    query = text("""
        SELECT
            id,
            intersection_id,
            CASE WHEN COALESCE(events::jsonb->0->>'source','') LIKE 'tomtom_%' THEN NULL ELSE total_vehicles END AS total_vehicles,
            average_speed,
            density,
            congestion_level,
            latitude,
            longitude,
            timestamp
        FROM traffic_stream_events
        WHERE location IS NOT NULL
        AND COALESCE(events::jsonb->0->>'source','') <> 'historical_chennai_arterial_benchmark'
        AND ST_DWithin(
            location::geography,
            ST_SetSRID(
                ST_MakePoint(
                    :longitude,
                    :latitude
                ),
                4326
            )::geography,
            :radius
        )
        ORDER BY timestamp DESC
        LIMIT 100
    """)

    result = db.execute(
        query,
        {
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius_meters
        }
    )

    return [
        dict(row._mapping)
        for row in result
    ]


@router.get("/zones")
def get_zones(
    db: Session = Depends(get_db)
):

    query = text("""
        SELECT
            zone_id,
            name,
            zone_type,
            ST_AsGeoJSON(
                geometry
            ) AS geometry
        FROM traffic_zones
    """)

    result = db.execute(query)

    return [
        dict(row._mapping)
        for row in result
    ]