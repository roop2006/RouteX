import json
from pathlib import Path

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

from ml.evaluation.metrics import (
    classification_metrics,
    regression_metrics
)


ARTIFACT_DIR = Path(
    "ml/artifacts"
)


def main():

    dataframe = load_routex_data()

    dataframe = validate_dataset(
        dataframe
    )

    dataframe = prepare_features(
        dataframe
    )

    _, _, test = time_split(
        dataframe
    )

    X_test = get_feature_matrix(
        test
    )

    classification_model = (
        joblib.load(
            ARTIFACT_DIR
            / "congestion_model.joblib"
        )
    )

    forecast_model = (
        joblib.load(
            ARTIFACT_DIR
            / "traffic_forecast_model.joblib"
        )
    )

    y_classification = test[
        "congestion_level"
    ]

    classification_prediction = (
        classification_model.predict(
            X_test
        )
    )

    classification_result = (
        classification_metrics(
            y_classification,
            classification_prediction
        )
    )

    y_forecast = test[
        "total_vehicles"
    ]

    forecast_prediction = (
        forecast_model.predict(
            X_test
        )
    )

    forecast_result = (
        regression_metrics(
            y_forecast,
            forecast_prediction
        )
    )

    results = {

        "classification":
            classification_result,

        "forecasting":
            forecast_result,

        "test_records":
            len(test)
    }

    with open(
        ARTIFACT_DIR
        / "final_metrics.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            indent=4
        )

    print(
        "\n=== FINAL TEST RESULTS ==="
    )

    print(
        "\nClassification:"
    )

    print(
        classification_result
    )

    print(
        "\nForecasting:"
    )

    print(
        forecast_result
    )


if __name__ == "__main__":
    main()
    