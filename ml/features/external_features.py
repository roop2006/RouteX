import pandas as pd


EXTERNAL_FEATURES = [
    "hour",
    "day_of_week",
    "month",
    "is_weekend",
    "is_peak_hour",
    "traffic_lag_1",
    "traffic_lag_2",
    "traffic_lag_3",
    "traffic_rolling_mean_3",
]


def prepare_external_features(
    dataframe,
    forecast_horizon=1,
):
    if forecast_horizon < 1:
        raise ValueError(
            "forecast_horizon must be at least 1."
        )

    df = dataframe.copy()

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    df["traffic_volume"] = pd.to_numeric(
        df["traffic_volume"],
        errors="coerce"
    )

    df = df.dropna(
        subset=[
            "timestamp",
            "traffic_volume",
        ]
    )

    df = df.sort_values(
        "timestamp"
    ).reset_index(drop=True)

    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["month"] = df["timestamp"].dt.month

    df["is_weekend"] = (
        df["day_of_week"] >= 5
    ).astype(int)

    df["is_peak_hour"] = (
        df["hour"].isin(
            [7, 8, 9, 16, 17, 18]
        )
    ).astype(int)

    # These features use only previous observations.
    df["traffic_lag_1"] = (
        df["traffic_volume"].shift(1)
    )

    df["traffic_lag_2"] = (
        df["traffic_volume"].shift(2)
    )

    df["traffic_lag_3"] = (
        df["traffic_volume"].shift(3)
    )

    df["traffic_rolling_mean_3"] = (
        df["traffic_volume"]
        .shift(1)
        .rolling(window=3)
        .mean()
    )

    # Target is future traffic volume.
    df["target_traffic_volume"] = (
        df["traffic_volume"].shift(
            -forecast_horizon
        )
    )

    df = df.dropna(
        subset=(
            EXTERNAL_FEATURES
            + ["target_traffic_volume"]
        )
    )

    return df
    