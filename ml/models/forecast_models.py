from sklearn.dummy import (
    DummyRegressor
)

from sklearn.linear_model import (
    LinearRegression
)

from sklearn.ensemble import (
    RandomForestRegressor,
    HistGradientBoostingRegressor
)


def get_forecasting_models():

    return {

        "baseline":
            DummyRegressor(
                strategy="mean"
            ),

        "linear_regression":
            LinearRegression(),

        "random_forest":
            RandomForestRegressor(
                n_estimators=200,
                max_depth=12,
                random_state=42
            ),

        "gradient_boosting":
            HistGradientBoostingRegressor(
                max_iter=200,
                learning_rate=0.08,
                max_depth=8,
                random_state=42
            )
    }
