import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import redis
import logging

from backend.app.core.database import get_db
from backend.app.services.live_traffic_service import live_traffic_service
from ml.prediction.predictor import (
    TrafficPredictor
)


router = APIRouter(
    prefix="/ai",
    tags=["AI Prediction", "AI Traffic"]
)


predictor = None
logger = logging.getLogger("routex.ai_live")


def get_predictor():

    global predictor

    if predictor is None:
        predictor = TrafficPredictor()

    return predictor


@router.get("/live-prediction")
@router.get("/live-prediction/")
def live_prediction(db: Session = Depends(get_db)):

    traffic_data = live_traffic_service.get_latest_live_traffic(db=db)

    if not traffic_data or traffic_data.get("status") == "UNAVAILABLE":
        raise HTTPException(
            status_code=404,
            detail="No live traffic data available in Redis or database"
        )

    try:

        now = datetime.now()

        timestamp_str = traffic_data.get("timestamp")
        event_time = now
        if timestamp_str:
            try:
                event_time = datetime.fromisoformat(timestamp_str)
            except Exception:
                event_time = now

        prediction_input = {
            "total_vehicles":
                traffic_data.get(
                    "total_vehicles",
                    0
                ),

            "average_speed":
                traffic_data.get(
                    "average_speed",
                    0
                ),

            "density":
                traffic_data.get(
                    "density",
                    0
                ),

            "hour":
                event_time.hour,

            "day_of_week":
                event_time.weekday(),

            "minute":
                event_time.minute
        }

        model = get_predictor()

        prediction = model.predict(
            prediction_input
        )

        if traffic_data.get("freshness") not in {"STALE", "HISTORICAL", "UNAVAILABLE"}:
            try:
                from backend.app.services.alert_service import process_alert_event
                provider_source = traffic_data.get("source", "unknown")
                source_timestamp = traffic_data.get("timestamp") or now.isoformat()
                process_alert_event(db, {
                    "source": "routex_production_predictor",
                    "source_event_id": f"ai:{provider_source}:{source_timestamp}",
                    "timestamp": source_timestamp,
                    "intersection_id": traffic_data.get("intersection_id"),
                    "latitude": traffic_data.get("latitude"),
                    "longitude": traffic_data.get("longitude"),
                    "total_vehicles": traffic_data.get("total_vehicles", 0),
                    "average_speed": traffic_data.get("average_speed", 0),
                    "free_flow_speed": traffic_data.get("free_flow_speed"),
                    "density": traffic_data.get("density", 0),
                    "congestion_level": traffic_data.get("congestion_level"),
                    "predicted_congestion": prediction.get("predicted_congestion"),
                    "details": {"model_name": "routex_production_predictor", "prediction_confidence": prediction.get("prediction_confidence")},
                })
            except Exception as alert_error:
                logger.warning("Live prediction completed; alert evaluation skipped: %s", alert_error)

        return {
            "traffic_data": traffic_data,

            "prediction": prediction,

            "timestamp":
                now.isoformat()
        }

    except FileNotFoundError as error:

        raise HTTPException(
            status_code=503,
            detail=str(error)
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )
