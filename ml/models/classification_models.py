from sklearn.dummy import DummyClassifier

from sklearn.linear_model import (
    LogisticRegression
)

from sklearn.ensemble import (
    RandomForestClassifier,
    HistGradientBoostingClassifier
)


def get_classification_models():

    return {

        "baseline":
            DummyClassifier(
                strategy="most_frequent"
            ),

        "logistic_regression":
            LogisticRegression(
                max_iter=1000,
                class_weight="balanced"
            ),

        "random_forest":
            RandomForestClassifier(
                n_estimators=200,
                max_depth=12,
                random_state=42,
                class_weight="balanced"
            ),

        "gradient_boosting":
            HistGradientBoostingClassifier(
                max_iter=200,
                learning_rate=0.08,
                max_depth=8,
                random_state=42
            )
    }
