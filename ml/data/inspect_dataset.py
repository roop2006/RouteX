from pathlib import Path

import pandas as pd


DATASET_PATH = Path(
    "data/datasets/raw/Metro_Interstate_Traffic_Volume.csv.gz"
)


def main():
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET_PATH}"
        )

    df = pd.read_csv(DATASET_PATH)

    print("\n=== DATASET INFORMATION ===")
    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")

    print("\n=== COLUMN NAMES ===")
    print(df.columns.tolist())

    print("\n=== DATA TYPES ===")
    print(df.dtypes)

    print("\n=== FIRST FIVE ROWS ===")
    print(df.head().to_string())

    print("\n=== MISSING VALUES ===")
    print(df.isna().sum())

    print("\n=== DUPLICATE ROWS ===")
    print(df.duplicated().sum())


if __name__ == "__main__":
    main()
