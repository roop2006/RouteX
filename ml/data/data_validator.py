import pandas as pd


REQUIRED_COLUMNS = [
    "timestamp",
    "total_vehicles",
    "average_speed",
    "density",
    "congestion_level"
]


def validate_columns(dataframe):

    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in dataframe.columns
    ]

    if missing:

        raise ValueError(
            f"Missing required columns: {missing}"
        )


def validate_values(dataframe):

    errors = []

    if (
        dataframe["total_vehicles"] < 0
    ).any():

        errors.append(
            "Negative vehicle count found"
        )

    if (
        dataframe["average_speed"] < 0
    ).any():

        errors.append(
            "Negative speed found"
        )

    if (
        (dataframe["density"] < 0)
        | (dataframe["density"] > 1)
    ).any():

        errors.append(
            "Density must be between 0 and 1"
        )

    valid_levels = {
        "LOW",
        "MEDIUM",
        "HIGH"
    }

    invalid_levels = set(
        dataframe["congestion_level"]
        .astype(str)
        .str.upper()
    ) - valid_levels

    if invalid_levels:

        errors.append(
            f"Invalid congestion levels: "
            f"{invalid_levels}"
        )

    if errors:

        raise ValueError(
            "Dataset validation failed:\n"
            + "\n".join(errors)
        )


def clean_dataset(dataframe):

    df = dataframe.copy()

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    df["total_vehicles"] = pd.to_numeric(
        df["total_vehicles"],
        errors="coerce"
    )

    df["average_speed"] = pd.to_numeric(
        df["average_speed"],
        errors="coerce"
    )

    df["density"] = pd.to_numeric(
        df["density"],
        errors="coerce"
    )

    df["congestion_level"] = (
        df["congestion_level"]
        .astype(str)
        .str.upper()
    )

    df = df.dropna(
        subset=[
            "timestamp",
            "total_vehicles",
            "average_speed",
            "density",
            "congestion_level"
        ]
    )

    df = df.drop_duplicates(
        subset=["timestamp", "intersection_id"]
    )

    df = df.sort_values(
        "timestamp"
    )

    return df


def validate_dataset(dataframe):

    if dataframe.empty:

        raise ValueError(
            "Dataset is empty."
        )

    validate_columns(dataframe)

    dataframe = clean_dataset(
        dataframe
    )

    validate_values(
        dataframe
    )

    return dataframe
