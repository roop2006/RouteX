import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import APIRouter, HTTPException
import redis

from ml.prediction.predictor import (
    TrafficPredictor
)

from vision.streaming.redis_client import (
    TrafficRedis
)


router = APIRouter(
    prefix="/ai",
    tags=["AI Prediction", "AI Traffic"]
)


redis_client = TrafficRedis()

predictor = None


def get_predictor():

    global predictor

    if predictor is None:
        predictor = TrafficPredictor()

    return predictor


@router.get("/live-prediction")
@router.get("/live-prediction/")
def live_prediction():

    try:
        traffic_data = (
            redis_client.get_latest()
        )
    except (redis.exceptions.RedisError, ConnectionError) as redis_err:
        raise HTTPException(
            status_code=503,
            detail=f"Redis service unavailable: {str(redis_err)}"
        )

    if traffic_data is None:

        raise HTTPException(
            status_code=404,
            detail="No live traffic data available in Redis"
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