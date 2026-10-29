import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from backend.app.models.prediction_history import PredictionHistory


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def record_prediction(
    db: Session,
    model_name: str,
    predicted_value: float,
    forecast_target: str = "total_vehicles",
    forecast_horizon: str = "1_step",
    model_version: str = "v1.0.0",
    predicted_congestion: Optional[str] = None,
    prediction_confidence: Optional[float] = None,
    intersection_id: Optional[str] = None,
    input_features: Optional[dict] = None,
    prediction_timestamp: Optional[datetime] = None,
) -> PredictionHistory:
    """Record a newly generated model prediction with PENDING evaluation status."""
    record = PredictionHistory(
        prediction_timestamp=prediction_timestamp or _utc_now(),
        model_name=model_name,
        model_version=model_version,
        forecast_target=forecast_target,
        forecast_horizon=forecast_horizon,
        predicted_value=float(predicted_value),
        predicted_congestion=predicted_congestion,
        prediction_confidence=prediction_confidence,
        actual_value=None,
        actual_congestion=None,
        actual_timestamp=None,
        evaluation_status="PENDING",
        absolute_error=None,
        squared_error=None,
        intersection_id=intersection_id,
        input_features=input_features,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def record_actual_observation(
    db: Session,
    prediction_id: int,
    actual_value: float,
    actual_congestion: Optional[str] = None,
    actual_timestamp: Optional[datetime] = None,
) -> Optional[PredictionHistory]:
    """
    Record ground truth observation for a prediction and compute evaluation error metrics.
    """
    record = db.get(PredictionHistory, prediction_id)
    if not record:
        return None

    actual_val = float(actual_value)
    abs_err = abs(actual_val - record.predicted_value)
    sq_err = float((actual_val - record.predicted_value) ** 2)

    record.actual_value = actual_val
    record.actual_congestion = actual_congestion
    record.actual_timestamp = actual_timestamp or _utc_now()
    record.evaluation_status = "EVALUATED"
    record.absolute_error = abs_err
    record.squared_error = sq_err

    db.commit()
    db.refresh(record)
    return record


def match_and_evaluate_predictions(
    db: Session,
    actual_value: float,
    intersection_id: Optional[str] = None,
    actual_congestion: Optional[str] = None,
    actual_timestamp: Optional[datetime] = None,
    tolerance_minutes: int = 15,
) -> list[PredictionHistory]:
    """
    Match pending predictions around the observation timestamp and evaluate them.
    """
    obs_time = actual_timestamp or _utc_now()
    window_start = obs_time - timedelta(minutes=tolerance_minutes)
    window_end = obs_time + timedelta(minutes=tolerance_minutes)

    query = select(PredictionHistory).where(
        PredictionHistory.evaluation_status == "PENDING",
        PredictionHistory.prediction_timestamp.between(window_start, window_end),
    )
    if intersection_id is not None:
        query = query.where(PredictionHistory.intersection_id == intersection_id)

    pending_records = db.scalars(query).all()
    evaluated = []
    for record in pending_records:
        record_actual_observation(
            db=db,
            prediction_id=record.id,
            actual_value=actual_value,
            actual_congestion=actual_congestion,
            actual_timestamp=obs_time,
        )
        evaluated.append(record)

    return evaluated


def get_prediction_history(
    db: Session,
    model_name: Optional[str] = None,
    evaluation_status: Optional[str] = None,
    intersection_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[PredictionHistory]:
    """Retrieve filtered prediction history records."""
    query = select(PredictionHistory)

    if model_name:
        query = query.where(PredictionHistory.model_name == model_name)
    if evaluation_status:
        query = query.where(PredictionHistory.evaluation_status == evaluation_status)
    if intersection_id:
        query = query.where(PredictionHistory.intersection_id == intersection_id)

    query = query.order_by(PredictionHistory.prediction_timestamp.desc()).offset(skip).limit(limit)
    return list(db.scalars(query).all())


def get_evaluation_metrics(
    db: Session,
    model_name: Optional[str] = None,
    forecast_target: Optional[str] = None,
) -> dict:
    """
    Compute actual-versus-predicted evaluation metrics across recorded predictions.
    """
    base_query = select(PredictionHistory)
    if model_name:
        base_query = base_query.where(PredictionHistory.model_name == model_name)
    if forecast_target:
        base_query = base_query.where(PredictionHistory.forecast_target == forecast_target)

    all_records = list(db.scalars(base_query).all())
    total_count = len(all_records)
    pending_count = sum(1 for r in all_records if r.evaluation_status == "PENDING")
    evaluated_records = [r for r in all_records if r.evaluation_status == "EVALUATED" and r.actual_value is not None]
    evaluated_count = len(evaluated_records)

    if evaluated_count == 0:
        return {
            "model_name": model_name or "all",
            "forecast_target": forecast_target or "all",
            "total_predictions": total_count,
            "pending_count": pending_count,
            "evaluated_count": 0,
            "mae": None,
            "rmse": None,
            "r2": None,
            "classification_accuracy": None,
        }

    abs_errors = [r.absolute_error for r in evaluated_records if r.absolute_error is not None]
    sq_errors = [r.squared_error for r in evaluated_records if r.squared_error is not None]

    mae = float(sum(abs_errors) / len(abs_errors)) if abs_errors else 0.0
    rmse = float(math.sqrt(sum(sq_errors) / len(sq_errors))) if sq_errors else 0.0

    # Calculate R2 if possible
    actual_values = [r.actual_value for r in evaluated_records]
    y_mean = sum(actual_values) / len(actual_values)
    ss_tot = sum((y - y_mean) ** 2 for y in actual_values)
    ss_res = sum(sq_errors) if sq_errors else 0.0
    r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 0 else (1.0 if ss_res == 0 else 0.0)

    # Classification accuracy for congestion levels
    cong_matches = [
        1 for r in evaluated_records
        if r.predicted_congestion and r.actual_congestion and r.predicted_congestion.upper() == r.actual_congestion.upper()
    ]
    total_cong_eval = sum(1 for r in evaluated_records if r.predicted_congestion and r.actual_congestion)
    accuracy = float(len(cong_matches) / total_cong_eval) if total_cong_eval > 0 else None

    return {
        "model_name": model_name or "all",
        "forecast_target": forecast_target or "all",
        "total_predictions": total_count,
        "pending_count": pending_count,
        "evaluated_count": evaluated_count,
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
        "classification_accuracy": round(accuracy, 4) if accuracy is not None else None,
    }
