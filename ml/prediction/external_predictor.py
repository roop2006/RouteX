"""
External Traffic Volume Predictor for RouteX Phase 7.

This module provides inference and evaluation utilities for the external
Metro Interstate Traffic Volume model (Random Forest Regressor).

INTEGRATION BOUNDARY:
- Target: Highway volume for the next sequential observation.
- Domain: Interstate highway (I-94 Minneapolis-St Paul).
- Distinction: This model is separate from RouteX's urban intersection models
  (congestion classifier and urban forecast regressor). It should not be fed
  YOLO detections or live intersection Redis streams directly unless converted
  to the appropriate highway lag schema.
"""
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Mapping

import joblib
import pandas as pd

from ml.features.external_features import EXTERNAL_FEATURES
from ml.evaluation.metrics import regression_metrics

ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "external"
MODEL_PATH = ARTIFACT_DIR / "traffic_volume_model.joblib"
METADATA_PATH = ARTIFACT_DIR / "external_model_metadata.json"


class ExternalTrafficPredictor:
    """Predictor for the external Metro Interstate traffic volume forecasting model."""

    def __init__(self, model_path: Path | str | None = None, metadata_path: Path | str | None = None):
        self.model_path = Path(model_path) if model_path else MODEL_PATH
        self.metadata_path = Path(metadata_path) if metadata_path else METADATA_PATH

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"External traffic volume model not found at {self.model_path}. "
                "Run python -m ml.training.train_external_models first."
            )

        self.model = joblib.load(self.model_path)
        # Single-observation API inference does not benefit from a worker pool and
        # remains deterministic/reliable in Windows services and constrained runtimes.
        if hasattr(self.model, "n_jobs"):
            self.model.n_jobs = 1
        self.metadata = self._load_metadata()
        self.expected_features = EXTERNAL_FEATURES

    def _load_metadata(self) -> dict:
        if self.metadata_path.exists():
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def prepare_features(self, data: Mapping[str, Any] | pd.DataFrame) -> pd.DataFrame:
        """
        Validate and arrange input features according to EXTERNAL_FEATURES schema.
        """
        if isinstance(data, pd.DataFrame):
            df = data.copy()
        else:
            df = pd.DataFrame([dict(data)])

        missing = [f for f in self.expected_features if f not in df.columns]
        if missing:
            raise ValueError(
                f"Missing required external forecasting features: {missing}. "
                f"Expected features in order: {self.expected_features}"
            )

        # Ensure correct column ordering and float conversion
        df_ordered = df[self.expected_features].copy()
        for col in self.expected_features:
            df_ordered[col] = pd.to_numeric(df_ordered[col], errors="coerce")
            if df_ordered[col].isna().any():
                raise ValueError(f"Feature column '{col}' contains NaN/non-numeric values.")

        return df_ordered

    def predict(self, data: Mapping[str, Any] | pd.DataFrame) -> dict:
        """
        Predict next observation traffic volume for single or batched records.
        """
        features_df = self.prepare_features(data)
        raw_predictions = self.model.predict(features_df)

        if len(raw_predictions) == 1:
            predicted_value = max(0.0, round(float(raw_predictions[0]), 2))
            return {
                "predicted_traffic_volume": predicted_value,
                "model_name": self.metadata.get("model_name", "random_forest"),
                "model_version": self.metadata.get("model_version", "v1.0.0"),
                "forecast_target": self.metadata.get("target", "next_observation_traffic_volume"),
                "forecast_horizon_observations": self.metadata.get("forecast_horizon_observations", 1),
                "features_used": self.expected_features,
            }
        else:
            return {
                "predicted_traffic_volumes": [max(0.0, round(float(v), 2)) for v in raw_predictions],
                "count": len(raw_predictions),
                "model_name": self.metadata.get("model_name", "random_forest"),
                "model_version": self.metadata.get("model_version", "v1.0.0"),
            }

    def evaluate(self, y_true, y_pred) -> dict:
        """Evaluate actual versus predicted traffic volume using regression metrics."""
        return regression_metrics(y_true, y_pred)
