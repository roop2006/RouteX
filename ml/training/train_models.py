from pathlib import Path
from datetime import datetime
import json
import joblib

from ml.data.dataset_loader import (
    load_routex_data
)

from ml.data.data_validator import (
    validate_dataset
)

from ml.features.feature_engineering import (
    prepare_features,
    get_feature_matrix
)

from ml.training.dataset_split import (
    time_split
)

from ml.models.classification_models import (
    get_classification_models
)

from ml.models.forecast_models import (
    get_forecasting_models
)

from ml.evaluation.metrics import (
    classification_metrics,
    regression_metrics
)

from ml.evaluation.experiment_tracker import (
    save_results
)


ARTIFACT_DIR = Path(
    "ml/artifacts"
)


def train_classification(
    train,
    validation
):

    X_train = get_feature_matrix(
        train
    )

    y_train = train[
        "congestion_level"
    ]

    X_validation = get_feature_matrix(
        validation
    )

    y_validation = validation[
        "congestion_level"
    ]

    results = []

    models = (
        get_classification_models()
    )

    for name, model in models.items():

        model.fit(
            X_train,
            y_train
        )

        predictions = model.predict(
            X_validation
        )

        metrics = classification_metrics(
            y_validation,
            predictions
        )

        result = {
            "model": name,
            "task": "classification",
            "metrics": metrics
        }

        results.append(
            result
        )

        print(
            f"\n{name}"
        )

        print(
            metrics
        )

    results.sort(
        key=lambda item:
        item["metrics"]["f1_macro"],
        reverse=True
    )

    best_name = results[0]["model"]

    best_model = models[
        best_name
    ]

    return (
        best_name,
        best_model,
        results
    )


def train_forecasting(
    train,
    validation
):

    X_train = get_feature_matrix(
        train
    )

    y_train = train[
        "total_vehicles"
    ]

    X_validation = get_feature_matrix(
        validation
    )

    y_validation = validation[
        "total_vehicles"
    ]

    results = []

    models = (
        get_forecasting_models()
    )

    for name, model in models.items():

        model.fit(
            X_train,
            y_train
        )

        predictions = model.predict(
            X_validation
        )

        metrics = regression_metrics(
            y_validation,
            predictions
        )

        result = {
            "model": name,
            "task": "forecasting",
            "metrics": metrics
        }

        results.append(
            result
        )

        print(
            f"\n{name}"
        )

        print(
            metrics
        )

    results.sort(
        key=lambda item:
        item["metrics"]["mae"]
    )

    best_name = results[0]["model"]

    best_model = models[
        best_name
    ]

    return (
        best_name,
        best_model,
        results
    )


def main():

    print(
        "Loading RouteX traffic data..."
    )

    dataframe = load_routex_data()

    dataframe = validate_dataset(
        dataframe
    )

    dataframe = prepare_features(
        dataframe
    )

    if len(dataframe) < 100:

        raise RuntimeError(
            "At least 100 valid records "
            "are recommended before training."
        )

    train, validation, test = (
        time_split(dataframe)
    )

    print(
        "\nDataset split:"
    )

    print(
        f"Train: {len(train)}"
    )

    print(
        f"Validation: {len(validation)}"
    )

    print(
        f"Test: {len(test)}"
    )

    print(
        "\n=== Classification ==="
    )

    (
        classification_name,
        classification_model,
        classification_results
    ) = train_classification(
        train,
        validation
    )

    print(
        "\n=== Forecasting ==="
    )

    (
        forecast_name,
        forecast_model,
        forecast_results
    ) = train_forecasting(
        train,
        validation
    )

    ARTIFACT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    joblib.dump(
        classification_model,
        ARTIFACT_DIR
        / "congestion_model.joblib"
    )

    joblib.dump(
        forecast_model,
        ARTIFACT_DIR
        / "traffic_forecast_model.joblib"
    )

    metadata = {

        "trained_at":
            datetime.now().isoformat(),

        "classification_model":
            classification_name,

        "forecast_model":
            forecast_name,

        "feature_count":
            len(
                get_feature_matrix(
                    dataframe
                ).columns
            ),

        "training_records":
            len(train),

        "validation_records":
            len(validation),

        "test_records":
            len(test)
    }

    with open(
        ARTIFACT_DIR
        / "model_metadata.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            metadata,
            file,
            indent=4
        )

    save_results(
        "classification_results.json",
        classification_results
    )

    save_results(
        "forecasting_results.json",
        forecast_results
    )

    print(
        "\nBest classification model:",
        classification_name
    )

    print(
        "Best forecasting model:",
        forecast_name
    )

    print(
        "\nModels saved successfully."
    )


if __name__ == "__main__":
    main()
    