from pathlib import Path

import pandas as pd


RAW_PATH = Path(
    "data/datasets/raw/Metro_Interstate_Traffic_Volume.csv"
)

OUTPUT_PATH = Path(
    "data/datasets/processed/metro_traffic.csv"
)


def prepare_external_dataset():
    if not RAW_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {RAW_PATH}"
        )

    df = pd.read_csv(RAW_PATH)

    required_columns = {
        "date_time",
        "traffic_volume",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    df = df.rename(
        columns={
            "date_time": "timestamp",
            "traffic_volume": "traffic_volume",
        }
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    df["traffic_volume"] = pd.to_numeric(
        df["traffic_volume"],
        errors="coerce"
    )

    # Remove invalid timestamps and targets.
    df = df.dropna(
        subset=[
            "timestamp",
            "traffic_volume",
        ]
    )

    # Traffic volume must be non-negative.
    df = df[
        df["traffic_volume"] >= 0
    ]

    # Preserve original weather columns if present.
    optional_columns = [
        "temp",
        "rain_1h",
        "snow_1h",
        "clouds_all",
        "holiday",
        "weather_main",
    ]

    selected_columns = [
        "timestamp",
        "traffic_volume",
    ]

    selected_columns += [
        column
        for column in optional_columns
        if column in df.columns
    ]

    df = df[selected_columns].copy()

    # Do not silently discard repeated timestamps:
    # they may represent repeated measurements.
    df = df.sort_values(
        "timestamp"
    ).reset_index(drop=True)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    df.to_csv(
        OUTPUT_PATH,
        index=False
    )

    print("External dataset prepared.")
    print(f"Valid rows: {len(df)}")
    print(f"Output: {OUTPUT_PATH}")

    print("\nTimestamp range:")
    print(df["timestamp"].min())
    print(df["timestamp"].max())

    print("\nTarget statistics:")
    print(df["traffic_volume"].describe())


if __name__ == "__main__":
    prepare_external_dataset()
