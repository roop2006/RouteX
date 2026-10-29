import pandas as pd


BASE_FEATURES = [
    "total_vehicles",
    "average_speed",
    "density",
    "hour",
    "minute",
    "day_of_week",
    "is_weekend",
    "is_peak_hour"
]


LAG_FEATURES = [
    "vehicles_lag_1",
    "vehicles_lag_2",
    "vehicles_lag_3",
    "speed_lag_1",
    "speed_lag_2",
    "density_lag_1",
    "density_lag_2"
]


def add_time_features(dataframe):

    df = dataframe.copy()

    df["timestamp"] = pd.to_datetime(
        df["timestamp"]
    )

    df["hour"] = (
        df["timestamp"].dt.hour
    )

    df["minute"] = (
        df["timestamp"].dt.minute
    )

    df["day_of_week"] = (
        df["timestamp"].dt.dayofweek
    )

    df["is_weekend"] = (
        df["day_of_week"] >= 5
    ).astype(int)

    df["is_peak_hour"] = (
        df["hour"].isin(
            [7, 8, 9, 17, 18, 19]
        )
    ).astype(int)

    return df


def add_vehicle_type_features(
    dataframe
):

    df = dataframe.copy()

    if "vehicle_types" not in df.columns:

        return df

    return df


def add_lag_features(
    dataframe,
    group_column="intersection_id"
):

    df = dataframe.copy()

    sort_columns = [
        group_column,
        "timestamp"
    ]

    df = df.sort_values(
        sort_columns
    )

    grouped = df.groupby(
        group_column,
        group_keys=False
    )

    df["vehicles_lag_1"] = (
        grouped["total_vehicles"]
        .shift(1)
    )

    df["vehicles_lag_2"] = (
        grouped["total_vehicles"]
        .shift(2)
    )

    df["vehicles_lag_3"] = (
        grouped["total_vehicles"]
        .shift(3)
    )

    df["speed_lag_1"] = (
        grouped["average_speed"]
        .shift(1)
    )

    df["speed_lag_2"] = (
        grouped["average_speed"]
        .shift(2)
    )

    df["density_lag_1"] = (
        grouped["density"]
        .shift(1)
    )

    df["density_lag_2"] = (
        grouped["density"]
        .shift(2)
    )

    return df


def prepare_features(
    dataframe
):

    df = dataframe.copy()

    df = add_time_features(
        df
    )

    df = add_vehicle_type_features(
        df
    )

    if "intersection_id" in df.columns:

        df = add_lag_features(
            df
        )

    df = df.dropna(
        subset=LAG_FEATURES
    )

    return df


FEATURE_COLUMNS = (
    BASE_FEATURES
    + LAG_FEATURES
)


def get_feature_matrix(
    dataframe
):

    missing = [
        column
        for column in FEATURE_COLUMNS
        if column not in dataframe.columns
    ]

    if missing:

        raise ValueError(
            f"Missing features: {missing}"
        )

    return dataframe[
        FEATURE_COLUMNS
    ]
