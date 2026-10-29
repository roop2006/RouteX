def time_split(
    dataframe,
    train_ratio=0.70,
    validation_ratio=0.15
):

    dataframe = dataframe.sort_values(
        "timestamp"
    ).reset_index(
        drop=True
    )

    total = len(dataframe)

    train_end = int(
        total * train_ratio
    )

    validation_end = int(
        total *
        (
            train_ratio
            + validation_ratio
        )
    )

    train = dataframe.iloc[
        :train_end
    ]

    validation = dataframe.iloc[
        train_end:validation_end
    ]

    test = dataframe.iloc[
        validation_end:
    ]

    return (
        train,
        validation,
        test
    )
