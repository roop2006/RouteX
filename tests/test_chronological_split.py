import pandas as pd
import pytest

from ml.training.external_split import split_time_series
from ml.training.dataset_split import time_split


def test_split_time_series_chronological_order():
    timestamps = pd.date_range("2026-01-01", periods=100, freq="h")
    df = pd.DataFrame({
        "timestamp": timestamps,
        "value": range(100)
    })
    # Shuffle order before splitting
    shuffled_df = df.sample(frac=1.0, random_state=42)

    train, val, test = split_time_series(shuffled_df, train_ratio=0.7, validation_ratio=0.15)

    assert len(train) == 70
    assert len(val) == 15
    assert len(test) == 15

    # Chronological guarantees: train max timestamp < val min timestamp < test min timestamp
    assert train["timestamp"].max() < val["timestamp"].min()
    assert val["timestamp"].max() < test["timestamp"].min()

    # Values must remain strictly ordered
    assert list(train["value"]) == list(range(70))
    assert list(val["value"]) == list(range(70, 85))
    assert list(test["value"]) == list(range(85, 100))


def test_split_time_series_invalid_ratios():
    df = pd.DataFrame({"timestamp": ["2026-01-01"], "value": [1]})
    with pytest.raises(ValueError, match="train_ratio must be between 0 and 1"):
        split_time_series(df, train_ratio=1.2)

    with pytest.raises(ValueError, match="sum to less than 1"):
        split_time_series(df, train_ratio=0.6, validation_ratio=0.5)


def test_time_split_routex():
    timestamps = pd.date_range("2026-01-01", periods=20, freq="h")
    df = pd.DataFrame({"timestamp": timestamps, "total_vehicles": range(20)})
    train, val, test = time_split(df, train_ratio=0.7, validation_ratio=0.15)
    assert len(train) + len(val) + len(test) == 20
    assert train["timestamp"].max() < val["timestamp"].min()
    assert val["timestamp"].max() < test["timestamp"].min()
