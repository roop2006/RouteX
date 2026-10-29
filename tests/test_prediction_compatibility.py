import pytest
from ml.prediction.predictor import TrafficPredictor
from ml.prediction.external_predictor import ExternalTrafficPredictor
from ml.features.external_features import EXTERNAL_FEATURES


def test_traffic_predictor_inference():
    predictor = TrafficPredictor()
    sample_input = {
        "total_vehicles": 18,
        "average_speed": 42.5,
        "density": 0.35,
        "hour": 14,
        "day_of_week": 2,
        "minute": 30,
    }
    result = predictor.predict(sample_input)

    assert "predicted_congestion" in result
    assert result["predicted_congestion"] in ["LOW", "MEDIUM", "HIGH"]
    assert "prediction_confidence" in result
    assert 0.0 <= result["prediction_confidence"] <= 1.0
    assert "predicted_vehicle_count" in result
    assert result["predicted_vehicle_count"] >= 0.0


def test_traffic_predictor_infers_missing_time_features():
    predictor = TrafficPredictor()
    # Missing hour, day_of_week, minute - should infer from current time without crashing
    sample_input = {
        "total_vehicles": 25,
        "average_speed": 30.0,
        "density": 0.6,
    }
    result = predictor.predict(sample_input)
    assert result["predicted_congestion"] in ["LOW", "MEDIUM", "HIGH"]
    assert result["predicted_vehicle_count"] >= 0.0


def test_external_traffic_predictor_inference():
    predictor = ExternalTrafficPredictor()
    sample_input = {
        "hour": 8,
        "day_of_week": 1,
        "month": 10,
        "is_weekend": 0,
        "is_peak_hour": 1,
        "traffic_lag_1": 4500,
        "traffic_lag_2": 4200,
        "traffic_lag_3": 3900,
        "traffic_rolling_mean_3": 4200.0,
    }
    result = predictor.predict(sample_input)
    assert "predicted_traffic_volume" in result
    assert result["predicted_traffic_volume"] > 0
    assert result["model_name"] == "random_forest"
    assert result["features_used"] == EXTERNAL_FEATURES


def test_external_traffic_predictor_rejects_missing_features():
    predictor = ExternalTrafficPredictor()
    invalid_input = {
        "hour": 8,
        "day_of_week": 1,
        # missing lag features
    }
    with pytest.raises(ValueError, match="Missing required external forecasting features"):
        predictor.predict(invalid_input)
