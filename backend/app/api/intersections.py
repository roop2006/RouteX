from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.database import get_db


router = APIRouter(
    prefix="/intersections",
    tags=["Intersections"]
)


@router.get("/")
def get_intersections(
    db: Session = Depends(get_db)
):

    query = text("""
        SELECT
            intersection_id,
            name,
            latitude,
            longitude,
            ST_AsGeoJSON(location)
                AS geometry
        FROM intersections
        ORDER BY intersection_id
    """)

    result = db.execute(query)

    return [
        dict(row._mapping)
        for row in result
    ]