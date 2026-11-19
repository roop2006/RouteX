from pathlib import Path

from ml.data.dataset_loader import (
    load_routex_data
)

from ml.data.data_validator import (
    validate_dataset
)


OUTPUT_PATH = Path(
    "data/datasets/processed/routex_traffic.csv"
)


def main():

    print(
        "Loading RouteX historical traffic..."
    )

    dataframe = load_routex_data()

    print(
        f"Raw records: {len(dataframe)}"
    )

    dataframe = validate_dataset(
        dataframe
    )

    print(
        f"Valid records: {len(dataframe)}"
    )

    print(
        "\nCongestion distribution:"
    )

    print(
        dataframe[
            "congestion_level"
        ].value_counts()
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    dataframe.to_csv(
        OUTPUT_PATH,
        index=False
    )

    print(
        f"\nDataset saved to: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
