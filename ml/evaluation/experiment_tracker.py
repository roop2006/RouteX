import json
from pathlib import Path


RESULTS_DIR = Path(
    "ml/experiments"
)


def save_results(
    filename,
    results
):

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    path = (
        RESULTS_DIR
        / filename
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            indent=4
        )

    return path
