import pandas as pd

from sqlalchemy import text

from backend.app.core.database import SessionLocal


def load_routex_data():

    db = SessionLocal()

    try:

        query = text("""
            SELECT
                id,
                intersection_id,
                total_vehicles,
                average_speed,
                density,
                congestion_level,
                latitude,
                longitude,
                timestamp
            FROM traffic_stream_events
            WHERE timestamp IS NOT NULL
            ORDER BY timestamp ASC
        """)

        result = db.execute(query)

        rows = result.mappings().all()

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows)

    finally:

        db.close()


def save_dataframe(
    dataframe,
    output_path
):

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    dataframe.to_csv(
        output_path,
        index=False
    )
