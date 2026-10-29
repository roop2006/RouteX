import pandas as pd
import pytest

from ml.data.data_validator import (
    validate_dataset,
    validate_columns,
    validate_values,
    clean_dataset,
    REQUIRED_COLUMNS,
)


def test_validate_columns_passes_on_valid_data():
    df = pd.DataFrame(columns=REQUIRED_COLUMNS)
    validate_columns(df)


def test_validate_columns_raises_on_missing_column():
    df = pd.DataFrame(columns=["timestamp", "total_vehicles"])
    with pytest.raises(ValueError, match="Missing required columns"):
        validate_columns(df)


def test_validate_values_detects_negative_vehicles():
    df = pd.DataFrame({
        "timestamp": ["2026-01-01 00:00:00"],
        "total_vehicles": [-5],
        "average_speed": [40.0],
        "density": [0.5],
        "congestion_level": ["LOW"],
    })
    with pytest.raises(ValueError, match="Negative vehicle count"):
        validate_values(df)


def test_validate_values_detects_invalid_density():
    df = pd.DataFrame({
        "timestamp": ["2026-01-01 00:00:00"],
        "total_vehicles": [10],
        "average_speed": [40.0],
        "density": [1.5],
        "congestion_level": ["LOW"],
    })
    with pytest.raises(ValueError, match="Density must be between 0 and 1"):
        validate_values(df)


def test_validate_values_detects_invalid_congestion_level():
    df = pd.DataFrame({
        "timestamp": ["2026-01-01 00:00:00"],
        "total_vehicles": [10],
        "average_speed": [40.0],
        "density": [0.5],
        "congestion_level": ["SUPER_CRITICAL"],
    })
    with pytest.raises(ValueError, match="Invalid congestion levels"):
        validate_values(df)


def test_clean_dataset_removes_nans_and_duplicates():
    df = pd.DataFrame({
        "timestamp": ["2026-01-01 00:00:00", "2026-01-01 00:00:00", "invalid_date", "2026-01-01 01:00:00"],
        "intersection_id": ["INT1", "INT1", "INT1", "INT1"],
        "total_vehicles": [10, 10, 20, 30],
        "average_speed": [45.0, 45.0, 40.0, None],
        "density": [0.2, 0.2, 0.4, 0.5],
        "congestion_level": ["LOW", "LOW", "MEDIUM", "MEDIUM"],
    })
    cleaned = clean_dataset(df)
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["total_vehicles"] == 10
