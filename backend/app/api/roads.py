from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.database import get_db


router = APIRouter(
    prefix="/roads",
    tags=["Roads"]
)


@router.get("/")
def get_roads(
    db: Session = Depends(get_db)
):

    query = text("""
        SELECT
            road_id,
            road_name,
            speed_limit,
            lanes,
            ST_AsGeoJSON(
                geometry
            ) AS geometry
        FROM road_segments
        ORDER BY road_id
    """)

    result = db.execute(query)

    return [
        dict(row._mapping)
        for row in result
    ]