import pandas as pd
import numpy as np
import pytest

from ml.features.feature_engineering import (
    add_time_features,
    add_lag_features,
    prepare_features,
    FEATURE_COLUMNS,
    BASE_FEATURES,
    LAG_FEATURES,
)
from ml.features.external_features import (
    prepare_external_features,
    EXTERNAL_FEATURES,
)


def test_add_time_features():
    df = pd.DataFrame({
        "timestamp": ["2026-03-02 08:30:00", "2026-03-07 14:00:00"]  # Monday 8:30 AM, Saturday 2:00 PM
    })
    result = add_time_features(df)
    assert result.iloc[0]["hour"] == 8
    assert result.iloc[0]["minute"] == 30
    assert result.iloc[0]["day_of_week"] == 0
    assert result.iloc[0]["is_weekend"] == 0
    assert result.iloc[0]["is_peak_hour"] == 1

    assert result.iloc[1]["hour"] == 14
    assert result.iloc[1]["minute"] == 0
    assert result.iloc[1]["day_of_week"] == 5
    assert result.iloc[1]["is_weekend"] == 1
    assert result.iloc[1]["is_peak_hour"] == 0


def test_add_lag_features_strictly_historical():
    df = pd.DataFrame({
        "intersection_id": ["INT1", "INT1", "INT1", "INT1"],
        "timestamp": pd.date_range("2026-01-01 00:00:00", periods=4, freq="h"),
        "total_vehicles": [10, 20, 30, 40],
        "average_speed": [50.0, 45.0, 40.0, 35.0],
        "density": [0.1, 0.2, 0.3, 0.4],
    })
    lagged = add_lag_features(df, group_column="intersection_id")

    # Row 0: all lags should be NaN
    assert np.isnan(lagged.iloc[0]["vehicles_lag_1"])

    # Row 1: lag_1 should be row 0's value (10)
    assert lagged.iloc[1]["vehicles_lag_1"] == 10
    assert lagged.iloc[1]["speed_lag_1"] == 50.0

    # Row 3: lag_1=30, lag_2=20, lag_3=10
    assert lagged.iloc[3]["vehicles_lag_1"] == 30
    assert lagged.iloc[3]["vehicles_lag_2"] == 20
    assert lagged.iloc[3]["vehicles_lag_3"] == 10


def test_external_features_and_target_alignment():
    # Synthetic time series with 10 steps
    timestamps = pd.date_range("2026-01-01 00:00:00", periods=10, freq="h")
    traffic = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    df = pd.DataFrame({
        "timestamp": timestamps,
        "traffic_volume": traffic,
    })

    featured = prepare_external_features(df, forecast_horizon=1)

    # First 3 rows dropped due to lag 3 / rolling 3
    # Last row dropped due to shift(-1) target
    assert len(featured) == 6

    # Verify column existence
    for col in EXTERNAL_FEATURES:
        assert col in featured.columns
    assert "target_traffic_volume" in featured.columns

    # For the first valid row (index corresponding to original index 3, traffic=400):
    first_valid = featured.iloc[0]
    # Lags must come from prior observations:
    assert first_valid["traffic_lag_1"] == 300
    assert first_valid["traffic_lag_2"] == 200
    assert first_valid["traffic_lag_3"] == 100
    assert first_valid["traffic_rolling_mean_3"] == pytest.approx((300 + 200 + 100) / 3)
    # Target is next observation: original index 4 traffic (500)
    assert first_valid["target_traffic_volume"] == 500


def test_external_features_invalid_horizon():
    df = pd.DataFrame({"timestamp": ["2026-01-01"], "traffic_volume": [100]})
    with pytest.raises(ValueError, match="forecast_horizon must be at least 1"):
        prepare_external_features(df, forecast_horizon=0)
