from pathlib import Path
from datetime import datetime
import json

import joblib
import numpy as np
import pandas as pd

from sklearn.dummy import DummyRegressor
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import (
    RandomForestRegressor,
    HistGradientBoostingRegressor,
)
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

from ml.features.external_features import (
    EXTERNAL_FEATURES,
    prepare_external_features,
)

from ml.training.external_split import (
    split_time_series,
)


INPUT_PATH = Path(
    "data/datasets/processed/metro_traffic.csv"
)

ARTIFACT_DIR = Path(
    "ml/artifacts/external"
)

EXPERIMENT_DIR = Path(
    "ml/experiments/external"
)


def calculate_metrics(y_true, predictions):
    return {
        "mae": float(
            mean_absolute_error(
                y_true,
                predictions,
            )
        ),
        "rmse": float(
            np.sqrt(
                mean_squared_error(
                    y_true,
                    predictions,
                )
            )
        ),
        "r2": float(
            r2_score(
                y_true,
                predictions,
            )
        ),
    }


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Prepared dataset not found: {INPUT_PATH}. "
            "Run python -m ml.data.prepare_external_dataset first."
        )

    raw_df = pd.read_csv(
        INPUT_PATH,
        parse_dates=["timestamp"],
    )

    df = prepare_external_features(
        raw_df,
        forecast_horizon=1,
    )

    if len(df) < 100:
        raise RuntimeError(
            "Insufficient usable time-series rows for this experiment."
        )

    train, validation, test = split_time_series(
        df,
    )

    X_train = train[EXTERNAL_FEATURES]
    y_train = train["target_traffic_volume"]

    X_validation = validation[EXTERNAL_FEATURES]
    y_validation = validation["target_traffic_volume"]

    X_test = test[EXTERNAL_FEATURES]
    y_test = test["target_traffic_volume"]

    models = {
        "previous_observation_baseline": None,

        "mean_baseline": DummyRegressor(
            strategy="mean",
        ),

        "linear_regression": LinearRegression(),

        "random_forest": RandomForestRegressor(
            n_estimators=200,
            max_depth=12,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        ),

        "hist_gradient_boosting": HistGradientBoostingRegressor(
            max_iter=200,
            learning_rate=0.08,
            max_leaf_nodes=31,
            early_stopping=False,
            random_state=42,
        ),
    }

    results = []
    fitted_models = {}

    print("\n=== DATA SPLIT ===")
    print(f"Training records: {len(train)}")
    print(f"Validation records: {len(validation)}")
    print(f"Test records: {len(test)}")

    for name, model in models.items():
        print(f"\nTraining: {name}")

        if name == "previous_observation_baseline":
            predictions = validation["traffic_lag_1"].to_numpy()
            fitted_models[name] = None
            iterations = 0

        else:
            model.fit(
                X_train,
                y_train,
            )

            predictions = model.predict(
                X_validation,
            )

            fitted_models[name] = model

            iterations = getattr(
                model,
                "n_iter_",
                None,
            )

            if iterations is None:
                iterations = getattr(
                    model,
                    "n_estimators",
                    None,
                )

        metrics = calculate_metrics(
            y_validation,
            predictions,
        )

        result = {
            "model": name,
            "validation_metrics": metrics,
            "training_iterations_or_estimators": (
                int(iterations)
                if isinstance(iterations, (int, np.integer))
                else iterations
            ),
        }

        results.append(result)

        print(f"Validation metrics: {metrics}")
        print(f"Iterations/estimators: {iterations}")

    # Lower validation MAE is better.
    results.sort(
        key=lambda item: item["validation_metrics"]["mae"]
    )

    best_result = results[0]
    best_name = best_result["model"]

    print("\n=== MODEL COMPARISON ===")

    for result in results:
        print(
            result["model"],
            result["validation_metrics"],
        )

    print(f"\nSelected model: {best_name}")

    # Evaluate the selected model once on the untouched test set.
    if best_name == "previous_observation_baseline":
        test_predictions = test["traffic_lag_1"].to_numpy()
        selected_model = None
    else:
        selected_model = fitted_models[best_name]

        test_predictions = selected_model.predict(
            X_test,
        )

    test_metrics = calculate_metrics(
        y_test,
        test_predictions,
    )

    print("\n=== FINAL TEST METRICS ===")
    print(test_metrics)

    ARTIFACT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    EXPERIMENT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Save a deployable model only if an ML estimator won.
    # If the naive baseline wins, do not pretend it is a trained model.
    if selected_model is not None:
        joblib.dump(
            selected_model,
            ARTIFACT_DIR / "traffic_volume_model.joblib",
        )

    model_params = (
        selected_model.get_params()
        if selected_model is not None and hasattr(selected_model, "get_params")
        else {}
    )

    metadata = {
        "model_name": best_name,
        "model_type": (
            type(selected_model).__name__
            if selected_model is not None
            else "Baseline"
        ),
        "model_version": "v1.0.0",
        "model_artifact_path": str((ARTIFACT_DIR / "traffic_volume_model.joblib").as_posix()),
        "dataset_name": "Metro Interstate Traffic Volume",
        "dataset_file": str(INPUT_PATH.as_posix()),
        "date_range": {
            "start": str(raw_df["timestamp"].min()),
            "end": str(raw_df["timestamp"].max()),
        },
        "splits": {
            "train": {
                "records": len(train),
                "start": str(train["timestamp"].min()),
                "end": str(train["timestamp"].max()),
            },
            "validation": {
                "records": len(validation),
                "start": str(validation["timestamp"].min()),
                "end": str(validation["timestamp"].max()),
            },
            "test": {
                "records": len(test),
                "start": str(test["timestamp"].min()),
                "end": str(test["timestamp"].max()),
            },
        },
        "training_records": len(train),
        "validation_records": len(validation),
        "test_records": len(test),
        "feature_names": list(EXTERNAL_FEATURES),
        "feature_order": list(EXTERNAL_FEATURES),
        "target": "next_observation_traffic_volume",
        "forecast_horizon_observations": 1,
        "forecasting_horizon_description": (
            "Forecasts traffic volume for the next sequential observation (1 step ahead). "
            "Timestamp frequency in the dataset is predominantly hourly with occasional "
            "repeated observations (e.g. weather reports) and time gaps."
        ),
        "model_parameters": model_params,
        "random_seed": 42,
        "validation_metrics": best_result["validation_metrics"],
        "final_test_metrics": test_metrics,
        "trained_at": datetime.now().isoformat(),
        "model_saved": selected_model is not None,
    }

    with open(
        ARTIFACT_DIR / "external_model_metadata.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metadata,
            file,
            indent=4,
        )

    experiment = {
        "dataset": "Metro Interstate Traffic Volume",
        "date_range": {
            "start": str(raw_df["timestamp"].min()),
            "end": str(raw_df["timestamp"].max()),
        },
        "features": list(EXTERNAL_FEATURES),
        "model_results": results,
        "selected_model": best_name,
        "selected_model_type": (
            type(selected_model).__name__
            if selected_model is not None
            else "Baseline"
        ),
        "selected_model_parameters": model_params,
        "random_seed": 42,
        "final_test_metrics": test_metrics,
        "timestamp": datetime.now().isoformat(),
    }

    with open(
        EXPERIMENT_DIR / "forecasting_results.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            experiment,
            file,
            indent=4,
        )

    print("\nArtifacts saved.")
    print(f"Model directory: {ARTIFACT_DIR}")
    print(f"Experiment directory: {EXPERIMENT_DIR}")


if __name__ == "__main__":
    main()
    