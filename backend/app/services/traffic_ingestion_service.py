"""
Traffic Ingestion Service for RouteX.
Handles ingestion, validation, normalization, and PostGIS spatial registration
for historical traffic datasets and observation callsets.
Preserves strict geographic provenance and prevents mixing unrelated datasets.
"""
from datetime import datetime
import io
import json
import logging
from pathlib import Path
from typing import Any, Optional

from geoalchemy2.elements import WKTElement
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal
from backend.app.core.geo_config import POSTGIS_SRID
from backend.app.models.traffic_stream_event import TrafficStreamEvent
from backend.app.models.intersection import Intersection
from ml.data.data_validator import validate_columns, clean_dataset

logger = logging.getLogger(__name__)


class TrafficIngestionService:
    @staticmethod
    def ingest_observations_dataframe(
        df: pd.DataFrame,
        db: Session,
        provenance: str,
        default_intersection_id: Optional[str] = None,
        default_latitude: Optional[float] = None,
        default_longitude: Optional[float] = None,
    ) -> dict[str, Any]:
        """
        Validates, normalizes, and stores traffic observations from a DataFrame.
        """
        if df.empty:
            return {"inserted": 0, "skipped": 0, "errors": ["DataFrame is empty."]}

        # Column normalization mapping
        col_rename = {}
        if "traffic_volume" in df.columns and "total_vehicles" not in df.columns:
            col_rename["traffic_volume"] = "total_vehicles"
        if "vehicle_count" in df.columns and "total_vehicles" not in df.columns:
            col_rename["vehicle_count"] = "total_vehicles"
        if "speed" in df.columns and "average_speed" not in df.columns:
            col_rename["speed"] = "average_speed"
        if col_rename:
            df = df.rename(columns=col_rename)

        # Ensure required columns exist
        for req in ["total_vehicles", "average_speed", "density", "congestion_level"]:
            if req not in df.columns:
                if req == "density":
                    # Derive density if missing: vehicle_count / 30.0 (3 lanes * 10 capacity)
                    df["density"] = df["total_vehicles"].apply(
                        lambda v: min(1.0, max(0.0, round(float(v) / 30.0, 3)))
                    )
                elif req == "congestion_level":
                    # Derive congestion if missing
                    def _derive_cong(row):
                        d = float(row.get("density", 0.0))
                        s = float(row.get("average_speed", 40.0))
                        if d >= 0.75 and s <= 15.0:
                            return "HIGH"
                        if d >= 0.45 and s <= 30.0:
                            return "MEDIUM"
                        return "LOW"
                    df["congestion_level"] = df.apply(_derive_cong, axis=1)
                elif req == "average_speed":
                    df["average_speed"] = 35.0

        if "timestamp" not in df.columns:
            df["timestamp"] = datetime.now()

        # Clean and validate
        df_cleaned = clean_dataset(df)

        inserted_count = 0
        skipped_count = 0
        errors = []

        now_str = datetime.now().isoformat()

        for _, row in df_cleaned.iterrows():
            try:
                lat = row.get("latitude")
                if pd.isna(lat) or lat is None:
                    lat = default_latitude
                else:
                    lat = float(lat)

                lng = row.get("longitude")
                if pd.isna(lng) or lng is None:
                    lng = default_longitude
                else:
                    lng = float(lng)

                inter_id = row.get("intersection_id")
                if pd.isna(inter_id) or not inter_id:
                    inter_id = default_intersection_id

                location = None
                if lat is not None and lng is not None:
                    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
                        skipped_count += 1
                        continue
                    location = WKTElement(f"POINT({lng} {lat})", srid=POSTGIS_SRID)

                ts = row["timestamp"]
                if isinstance(ts, str):
                    event_dt = pd.to_datetime(ts).to_pydatetime()
                elif hasattr(ts, "to_pydatetime"):
                    event_dt = ts.to_pydatetime()
                else:
                    event_dt = ts

                metadata = {
                    "source": "historical_ingestion",
                    "provenance": provenance,
                    "imported_at": now_str,
                }

                event = TrafficStreamEvent(
                    total_vehicles=int(row["total_vehicles"]),
                    vehicle_types={"car": int(row["total_vehicles"])},
                    lane_counts={},
                    direction_counts={},
                    average_speed=float(row["average_speed"]),
                    density=float(row["density"]),
                    congestion_level=str(row["congestion_level"]).upper(),
                    events=[metadata],
                    intersection_id=inter_id,
                    latitude=lat,
                    longitude=lng,
                    location=location,
                    timestamp=event_dt,
                )
                db.add(event)
                inserted_count += 1
            except Exception as row_err:
                errors.append(str(row_err))
                skipped_count += 1

        db.commit()
        return {
            "inserted": inserted_count,
            "skipped": skipped_count,
            "errors": errors[:5],
            "provenance": provenance,
        }

    @classmethod
    def ingest_csv_file(
        cls,
        file_path: Path | str,
        provenance: str,
        db: Optional[Session] = None,
        default_intersection_id: Optional[str] = None,
        default_latitude: Optional[float] = None,
        default_longitude: Optional[float] = None,
    ) -> dict[str, Any]:
        """Reads a CSV file from disk and ingests it."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")

        df = pd.read_csv(path)
        owns_session = False
        if db is None:
            db = SessionLocal()
            owns_session = True

        try:
            return cls.ingest_observations_dataframe(
                df=df,
                db=db,
                provenance=provenance,
                default_intersection_id=default_intersection_id,
                default_latitude=default_latitude,
                default_longitude=default_longitude,
            )
        finally:
            if owns_session:
                db.close()


def seed_corridor_historical_observations(db: Session) -> dict[str, int]:
    """Compatibility entry point: only explicitly imported observations are valid.

    Older releases inserted fixed profiles here. Existing records are preserved
    but excluded from operational route analytics by their provenance.
    """
    return {"observations_added": 0}
