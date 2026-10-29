from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict, Field


class ActualObservationUpdate(BaseModel):
    actual_value: float = Field(..., description="Actual observed traffic volume / count")
    actual_congestion: Optional[str] = Field(None, description="Actual observed congestion level (LOW, MEDIUM, HIGH)")
    actual_timestamp: Optional[datetime] = Field(None, description="Observation timestamp (defaults to current time)")


class MatchEvaluationRequest(BaseModel):
    actual_value: float = Field(..., description="Actual observed traffic volume / count")
    intersection_id: Optional[str] = Field(None, description="Intersection identifier to match pending predictions")
    actual_congestion: Optional[str] = Field(None, description="Actual congestion level")
    actual_timestamp: Optional[datetime] = Field(None, description="Observation timestamp")
    tolerance_minutes: int = Field(15, ge=1, le=1440, description="Time window tolerance for matching predictions")


class PredictionHistoryResponse(BaseModel):
    id: int
    prediction_timestamp: datetime
    model_name: str
    model_version: str
    forecast_target: str
    forecast_horizon: str
    predicted_value: float
    predicted_congestion: Optional[str] = None
    prediction_confidence: Optional[float] = None
    actual_value: Optional[float] = None
    actual_congestion: Optional[str] = None
    actual_timestamp: Optional[datetime] = None
    evaluation_status: str
    absolute_error: Optional[float] = None
    squared_error: Optional[float] = None
    intersection_id: Optional[str] = None
    input_features: Optional[dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class EvaluationMetricsResponse(BaseModel):
    model_name: str
    forecast_target: str
    total_predictions: int
    pending_count: int
    evaluated_count: int
    mae: Optional[float] = None
    rmse: Optional[float] = None
    r2: Optional[float] = None
    classification_accuracy: Optional[float] = None
