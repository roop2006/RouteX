import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd

from ml.features.feature_engineering import FEATURE_COLUMNS
from ml.models.congestion_model import (
    CongestionModel
)
from ml.models.traffic_forecast_model import (
    TrafficForecastModel
)


class TrafficPredictor:

    def __init__(self):

        congestion_path = (
            Path(__file__).resolve().parent.parent
            / "artifacts"
            / "congestion_model.joblib"
        )

        forecast_path = (
            Path(__file__).resolve().parent.parent
            / "artifacts"
            / "traffic_forecast_model.joblib"
        )

        if not congestion_path.exists():

            raise FileNotFoundError(
                "Congestion model not found. "
                "Run model training first."
            )

        if not forecast_path.exists():

            raise FileNotFoundError(
                "Traffic forecast model not found. "
                "Run model training first."
            )

        self.congestion_model = (
            CongestionModel()
        )

        self.forecast_model = (
            TrafficForecastModel()
        )

        self.congestion_model.load()

        self.forecast_model.load()

    def predict(self, traffic_data):

        data_dict = dict(traffic_data)

        # Derive time features if missing from timestamp or current time
        if any(col not in data_dict or data_dict[col] is None for col in ["hour", "day_of_week", "minute"]):
            ts = data_dict.get("timestamp")
            if ts:
                try:
                    dt = pd.to_datetime(ts)
                except Exception:
                    dt = datetime.now()
            else:
                dt = datetime.now()

            if "hour" not in data_dict or data_dict["hour"] is None:
                data_dict["hour"] = dt.hour
            if "day_of_week" not in data_dict or data_dict["day_of_week"] is None:
                data_dict["day_of_week"] = dt.weekday() if hasattr(dt, "weekday") else dt.dayofweek
            if "minute" not in data_dict or data_dict["minute"] is None:
                data_dict["minute"] = dt.minute

        dataframe = pd.DataFrame(
            [data_dict]
        )

        for col in FEATURE_COLUMNS:
            if col not in dataframe.columns:
                dataframe[col] = 0
            else:
                dataframe[col] = (
                    pd.to_numeric(
                        dataframe[col],
                        errors="coerce"
                    )
                    .fillna(0)
                )

        features = dataframe[
            FEATURE_COLUMNS
        ]

        congestion = (
            self.congestion_model.predict(
                features
            )[0]
        )

        probabilities = (
            self.congestion_model.predict_proba(
                features
            )[0]
        )

        confidence = float(
            max(probabilities)
        )

        predicted_vehicles = float(
            self.forecast_model.predict(
                features
            )[0]
        )

        return {
            "predicted_congestion":
                str(congestion),

            "prediction_confidence":
                round(confidence, 4),

            "predicted_vehicle_count":
                max(0.0, round(
                    predicted_vehicles,
                    2
                ))
        }