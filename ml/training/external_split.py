def split_time_series(
    dataframe,
    train_ratio=0.70,
    validation_ratio=0.15,
):
    if not 0 < train_ratio < 1:
        raise ValueError(
            "train_ratio must be between 0 and 1."
        )

    if not 0 < validation_ratio < 1:
        raise ValueError(
            "validation_ratio must be between 0 and 1."
        )

    if train_ratio + validation_ratio >= 1:
        raise ValueError(
            "Train and validation ratios must sum to less than 1."
        )

    df = dataframe.sort_values(
        "timestamp"
    ).reset_index(drop=True)

    total = len(df)

    train_end = int(
        total * train_ratio
    )

    validation_end = int(
        total * (
            train_ratio + validation_ratio
        )
    )

    train = df.iloc[:train_end].copy()

    validation = df.iloc[
        train_end:validation_end
    ].copy()

    test = df.iloc[
        validation_end:
    ].copy()

    if min(
        len(train),
        len(validation),
        len(test),
    ) == 0:
        raise ValueError(
            "Insufficient records for the requested split."
        )

    return train, validation, test
    