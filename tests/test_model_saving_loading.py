import json
from pathlib import Path
import joblib
import pytest

from ml.features.feature_engineering import FEATURE_COLUMNS
from ml.features.external_features import EXTERNAL_FEATURES


def test_production_congestion_model_loads_and_has_correct_features():
    path = Path("ml/artifacts/congestion_model.joblib")
    assert path.exists(), "congestion_model.joblib must exist"
    model = joblib.load(path)
    assert hasattr(model, "predict")
    assert hasattr(model, "predict_proba")
    if hasattr(model, "feature_names_in_"):
        assert list(model.feature_names_in_) == list(FEATURE_COLUMNS)


def test_production_forecast_model_loads_and_has_correct_features():
    path = Path("ml/artifacts/traffic_forecast_model.joblib")
    assert path.exists(), "traffic_forecast_model.joblib must exist"
    model = joblib.load(path)
    assert hasattr(model, "predict")
    if hasattr(model, "feature_names_in_"):
        assert list(model.feature_names_in_) == list(FEATURE_COLUMNS)


def test_external_traffic_volume_model_loads():
    path = Path("ml/artifacts/external/traffic_volume_model.joblib")
    assert path.exists(), "External traffic volume model must exist"
    model = joblib.load(path)
    assert hasattr(model, "predict")
    if hasattr(model, "feature_names_in_"):
        assert list(model.feature_names_in_) == list(EXTERNAL_FEATURES)


def test_external_metadata_structure():
    path = Path("ml/artifacts/external/external_model_metadata.json")
    assert path.exists(), "external_model_metadata.json must exist"
    with open(path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    required_keys = [
        "model_name",
        "model_type",
        "model_version",
        "model_artifact_path",
        "dataset_name",
        "date_range",
        "training_records",
        "validation_records",
        "test_records",
        "feature_names",
        "feature_order",
        "target",
        "forecast_horizon_observations",
        "model_parameters",
        "validation_metrics",
        "final_test_metrics",
        "trained_at",
        "random_seed",
    ]
    for key in required_keys:
        assert key in meta, f"Missing required metadata key: {key}"

    assert meta["model_name"] == "random_forest"
    assert meta["model_type"] == "RandomForestRegressor"
    assert meta["feature_order"] == list(EXTERNAL_FEATURES)
    assert meta["validation_metrics"]["mae"] < 300
    assert meta["final_test_metrics"]["mae"] < 300
