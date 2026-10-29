from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base
from backend.app.models.prediction_history import PredictionHistory
from backend.app.services.prediction_history_service import (
    record_prediction,
    record_actual_observation,
    match_and_evaluate_predictions,
    get_prediction_history,
    get_evaluation_metrics,
)


@pytest.fixture
def db_session():
    """Create an isolated in-memory SQLite session for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    PredictionHistory.__table__.create(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        PredictionHistory.__table__.drop(bind=engine)


def test_record_prediction(db_session):
    record = record_prediction(
        db=db_session,
        model_name="routex_test_model",
        predicted_value=25.0,
        forecast_target="total_vehicles",
        predicted_congestion="MEDIUM",
        prediction_confidence=0.88,
        intersection_id="INT-TEST",
    )
    assert record.id is not None
    assert record.evaluation_status == "PENDING"
    assert record.predicted_value == 25.0
    assert record.actual_value is None


def test_record_actual_observation_computes_errors(db_session):
    record = record_prediction(
        db=db_session,
        model_name="routex_test_model",
        predicted_value=30.0,
        predicted_congestion="HIGH",
    )

    evaluated = record_actual_observation(
        db=db_session,
        prediction_id=record.id,
        actual_value=34.0,
        actual_congestion="HIGH",
    )

    assert evaluated.evaluation_status == "EVALUATED"
    assert evaluated.actual_value == 34.0
    assert evaluated.absolute_error == 4.0
    assert evaluated.squared_error == 16.0


def test_match_and_evaluate_predictions(db_session):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Record prediction within 5 minutes of now
    record_prediction(
        db=db_session,
        model_name="routex_test_model",
        predicted_value=15.0,
        intersection_id="INT-42",
        prediction_timestamp=now - timedelta(minutes=3),
    )
    # Record prediction far in the past (outside 15-min tolerance)
    record_prediction(
        db=db_session,
        model_name="routex_test_model",
        predicted_value=50.0,
        intersection_id="INT-42",
        prediction_timestamp=now - timedelta(hours=2),
    )

    evaluated_list = match_and_evaluate_predictions(
        db=db_session,
        intersection_id="INT-42",
        actual_value=18.0,
        actual_timestamp=now,
        tolerance_minutes=15,
    )

    assert len(evaluated_list) == 1
    assert evaluated_list[0].predicted_value == 15.0
    assert evaluated_list[0].actual_value == 18.0
    assert evaluated_list[0].absolute_error == 3.0


def test_get_evaluation_metrics_aggregation(db_session):
    # Empty case
    empty_metrics = get_evaluation_metrics(db=db_session)
    assert empty_metrics["total_predictions"] == 0
    assert empty_metrics["evaluated_count"] == 0
    assert empty_metrics["mae"] is None

    # Record and evaluate two predictions
    p1 = record_prediction(
        db=db_session,
        model_name="model_a",
        predicted_value=10.0,
        predicted_congestion="LOW",
    )
    p2 = record_prediction(
        db=db_session,
        model_name="model_a",
        predicted_value=20.0,
        predicted_congestion="MEDIUM",
    )
    # Leave p3 pending
    record_prediction(
        db=db_session,
        model_name="model_a",
        predicted_value=30.0,
        predicted_congestion="HIGH",
    )

    record_actual_observation(db=db_session, prediction_id=p1.id, actual_value=12.0, actual_congestion="LOW")
    record_actual_observation(db=db_session, prediction_id=p2.id, actual_value=22.0, actual_congestion="HIGH")

    metrics = get_evaluation_metrics(db=db_session, model_name="model_a")
    assert metrics["total_predictions"] == 3
    assert metrics["pending_count"] == 1
    assert metrics["evaluated_count"] == 2
    # Errors: |12-10| = 2, |22-20| = 2 -> MAE = 2.0
    assert metrics["mae"] == 2.0
    assert metrics["rmse"] == 2.0
    # 1 of 2 matches congestion ("LOW"=="LOW", "MEDIUM"!="HIGH")
    assert metrics["classification_accuracy"] == 0.5
