import pytest
from ml.evaluation.metrics import (
    classification_metrics,
    regression_metrics,
)


def test_classification_metrics_perfect():
    y_true = ["LOW", "MEDIUM", "HIGH", "LOW"]
    y_pred = ["LOW", "MEDIUM", "HIGH", "LOW"]
    metrics = classification_metrics(y_true, y_pred)
    assert metrics["accuracy"] == 1.0
    assert metrics["precision_macro"] == 1.0
    assert metrics["recall_macro"] == 1.0
    assert metrics["f1_macro"] == 1.0


def test_classification_metrics_imperfect():
    y_true = ["LOW", "MEDIUM", "HIGH", "LOW"]
    y_pred = ["LOW", "LOW", "HIGH", "LOW"]
    metrics = classification_metrics(y_true, y_pred)
    assert metrics["accuracy"] == 0.75
    assert 0.0 < metrics["f1_macro"] < 1.0


def test_regression_metrics_perfect():
    y_true = [10.0, 20.0, 30.0, 40.0]
    y_pred = [10.0, 20.0, 30.0, 40.0]
    metrics = regression_metrics(y_true, y_pred)
    assert metrics["mae"] == 0.0
    assert metrics["rmse"] == 0.0
    assert metrics["r2"] == 1.0


def test_regression_metrics_calculated():
    y_true = [10.0, 20.0, 30.0]
    y_pred = [12.0, 19.0, 33.0]
    metrics = regression_metrics(y_true, y_pred)
    # Errors: [2, 1, 3] -> MAE = 2.0
    # Squared: [4, 1, 9] -> MSE = 14/3 -> RMSE = sqrt(14/3)
    assert metrics["mae"] == pytest.approx(2.0)
    assert metrics["rmse"] == pytest.approx((14.0 / 3.0) ** 0.5)
    assert metrics["r2"] > 0.0
