import pandas as pd


def adapt_external_dataset(
    dataframe,
    column_mapping
):

    df = dataframe.rename(
        columns=column_mapping
    )

    required = [
        "timestamp",
        "total_vehicles",
        "average_speed",
        "density",
        "congestion_level"
    ]

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:

        raise ValueError(
            f"External dataset is missing: "
            f"{missing}"
        )

    return df[required].copy()
