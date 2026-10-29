from pathlib import Path

import joblib

from sklearn.ensemble import RandomForestClassifier


MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "artifacts"
    / "congestion_model.joblib"
)


class CongestionModel:

    def __init__(self):

        self.model = RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            random_state=42,
            class_weight="balanced"
        )

    def train(self, X, y):

        self.model.fit(X, y)

    def predict(self, X):

        return self.model.predict(X)

    def predict_proba(self, X):

        return self.model.predict_proba(X)

    def save(self):

        MODEL_PATH.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        joblib.dump(
            self.model,
            MODEL_PATH
        )

    def load(self):

        self.model = joblib.load(
            MODEL_PATH
        )