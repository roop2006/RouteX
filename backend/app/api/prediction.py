import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.prediction_history import (
    ActualObservationUpdate,
    MatchEvaluationRequest,
    PredictionHistoryResponse,
    EvaluationMetricsResponse,
)
from backend.app.services.prediction_history_service import (
    record_prediction,
    record_actual_observation,
    match_and_evaluate_predictions,
    get_prediction_history as fetch_prediction_history,
    get_evaluation_metrics,
)
from ml.prediction.predictor import (
    TrafficPredictor
)


router = APIRouter(
    prefix="/prediction",
    tags=["AI Prediction"]
)


class TrafficPredictionRequest(BaseModel):

    total_vehicles: int = Field(
        ge=0,
        description="Total vehicle count"
    )

    average_speed: float = Field(
        ge=0,
        description="Average speed in km/h"
    )

    density: float = Field(
        ge=0,
        le=1,
        description="Traffic density ratio (0 to 1)"
    )

    hour: int | None = Field(
        default=None,
        ge=0,
        le=23,
        description="Hour of day (0-23). Defaults to current hour if omitted."
    )

    day_of_week: int | None = Field(
        default=None,
        ge=0,
        le=6,
        description="Day of week (0=Monday, 6=Sunday). Defaults to current day if omitted."
    )

    minute: int | None = Field(
        default=None,
        ge=0,
        le=59,
        description="Minute (0-59). Defaults to current minute if omitted."
    )

    intersection_id: str | None = Field(
        default=None,
        description="Optional intersection identifier for localized tracking."
    )


predictor = None


def get_predictor():

    global predictor

    if predictor is None:

        predictor = TrafficPredictor()

    return predictor


@router.post("")
@router.post("/")
def predict_traffic(
    request: TrafficPredictionRequest,
    db: Session = Depends(get_db)
):

    try:

        now = datetime.now()

        hour = request.hour if request.hour is not None else now.hour
        day_of_week = request.day_of_week if request.day_of_week is not None else now.weekday()
        minute = request.minute if request.minute is not None else now.minute

        data = {
            "total_vehicles":
                request.total_vehicles,

            "average_speed":
                request.average_speed,

            "density":
                request.density,

            "hour":
                hour,

            "day_of_week":
                day_of_week,

            "minute":
                minute
        }

        model = get_predictor()

        prediction = model.predict(
            data
        )

        # Safely persist prediction to history (fails gracefully if DB is unavailable)
        try:
            record_prediction(
                db=db,
                model_name="routex_production_predictor",
                predicted_value=prediction["predicted_vehicle_count"],
                forecast_target="total_vehicles",
                forecast_horizon="1_step",
                model_version="v1.0.0",
                predicted_congestion=prediction.get("predicted_congestion"),
                prediction_confidence=prediction.get("prediction_confidence"),
                intersection_id=request.intersection_id,
                input_features=data,
                prediction_timestamp=now,
            )
        except Exception:
            # Non-blocking logging to guarantee prediction endpoint never fails on DB recording
            pass

        return {
            "input": {
                "total_vehicles": request.total_vehicles,
                "average_speed": request.average_speed,
                "density": request.density,
                "hour": hour,
                "day_of_week": day_of_week,
                "minute": minute
            },
            "prediction": prediction,
            "timestamp": now.isoformat()
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


@router.get("/history", response_model=list[PredictionHistoryResponse])
def get_history(
    model_name: str | None = None,
    evaluation_status: str | None = None,
    intersection_id: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Retrieve prediction history records with optional filters."""
    try:
        return fetch_prediction_history(
            db=db,
            model_name=model_name,
            evaluation_status=evaluation_status,
            intersection_id=intersection_id,
            skip=skip,
            limit=limit,
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Failed to fetch history: {str(error)}")


@router.post("/evaluate/{prediction_id}", response_model=PredictionHistoryResponse)
def evaluate_single_prediction(
    prediction_id: int,
    actual: ActualObservationUpdate,
    db: Session = Depends(get_db)
):
    """
    Record actual observation for a specific prediction ID and compute actual-versus-predicted error.
    """
    try:
        record = record_actual_observation(
            db=db,
            prediction_id=prediction_id,
            actual_value=actual.actual_value,
            actual_congestion=actual.actual_congestion,
            actual_timestamp=actual.actual_timestamp,
        )
        if not record:
            raise HTTPException(status_code=404, detail=f"Prediction with ID {prediction_id} not found")
        return record
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(error)}")


@router.post("/evaluate-by-match", response_model=list[PredictionHistoryResponse])
def evaluate_matching_predictions(
    request: MatchEvaluationRequest,
    db: Session = Depends(get_db)
):
    """
    Match pending predictions around the observation timestamp and evaluate them.
    """
    try:
        evaluated = match_and_evaluate_predictions(
            db=db,
            actual_value=request.actual_value,
            intersection_id=request.intersection_id,
            actual_congestion=request.actual_congestion,
            actual_timestamp=request.actual_timestamp,
            tolerance_minutes=request.tolerance_minutes,
        )
        return evaluated
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Match evaluation failed: {str(error)}")


@router.get("/metrics", response_model=EvaluationMetricsResponse)
def get_prediction_metrics(
    model_name: str | None = None,
    forecast_target: str | None = None,
    db: Session = Depends(get_db)
):
    """
    Get aggregated actual-versus-predicted evaluation metrics (MAE, RMSE, R2, accuracy).
    """
    try:
        metrics = get_evaluation_metrics(
            db=db,
            model_name=model_name,
            forecast_target=forecast_target,
        )
        return metrics
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Failed to calculate metrics: {str(error)}")


@router.get("/models")
def get_model_registry():
    """
    List available ML models, their artifacts, feature schemas, and deployment status.
    Maintains clean boundaries between RouteX production models and external forecasting models.
    """
    return {
        "production_models": [
            {
                "name": "congestion_model",
                "type": "RandomForestClassifier",
                "target": "congestion_level (LOW, MEDIUM, HIGH)",
                "artifact_path": "ml/artifacts/congestion_model.joblib",
                "features_count": 15,
                "status": "active_in_production",
                "domain": "urban_intersections",
            },
            {
                "name": "traffic_forecast_model",
                "type": "RandomForestRegressor",
                "target": "total_vehicles",
                "artifact_path": "ml/artifacts/traffic_forecast_model.joblib",
                "features_count": 15,
                "status": "active_in_production",
                "domain": "urban_intersections",
            },
        ],
        "external_models": [
            {
                "name": "traffic_volume_model",
                "type": "RandomForestRegressor",
                "target": "next_observation_traffic_volume",
                "artifact_path": "ml/artifacts/external/traffic_volume_model.joblib",
                "metadata_path": "ml/artifacts/external/external_model_metadata.json",
                "features_count": 9,
                "status": "evaluated_independently",
                "domain": "interstate_highway_corridor",
                "integration_boundary": (
                    "Evaluated independently on Metro Interstate dataset. "
                    "Not deployed to live intersection streams without schema adaptation."
                ),
            }
        ]
    }