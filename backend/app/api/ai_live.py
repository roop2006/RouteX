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
