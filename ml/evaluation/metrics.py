from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score
)

import numpy as np


def classification_metrics(
    y_true,
    y_pred
):

    return {

        "accuracy":
            float(
                accuracy_score(
                    y_true,
                    y_pred
                )
            ),

        "precision_macro":
            float(
                precision_score(
                    y_true,
                    y_pred,
                    average="macro",
                    zero_division=0
                )
            ),

        "recall_macro":
            float(
                recall_score(
                    y_true,
                    y_pred,
                    average="macro",
                    zero_division=0
                )
            ),

        "f1_macro":
            float(
                f1_score(
                    y_true,
                    y_pred,
                    average="macro",
                    zero_division=0
                )
            )
    }


def regression_metrics(
    y_true,
    y_pred
):

    rmse = np.sqrt(
        mean_squared_error(
            y_true,
            y_pred
        )
    )

    return {

        "mae":
            float(
                mean_absolute_error(
                    y_true,
                    y_pred
                )
            ),

        "rmse":
            float(rmse),

        "r2":
            float(
                r2_score(
                    y_true,
                    y_pred
                )
            )
    }
