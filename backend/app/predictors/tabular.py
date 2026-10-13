"""
Tabular (sklearn Pipeline) predictor. One instance per modality-model (diabetes_lab,
diabetes_clinical, hypertension_clinical). Loading never raises past __init__ callers
that catch it - a missing/corrupt joblib is handled by the registry, which marks the
slot 'missing'/'error' and leaves everything else running.
"""
from pathlib import Path

import joblib
import pandas as pd
import sklearn


class TabularPredictor:
    def __init__(self, joblib_path: Path, meta: dict):
        self.pipeline = joblib.load(joblib_path)
        self.meta = meta
        self.features: list[str] = meta["features"]
        self.threshold: float = meta["threshold"]
        self.reference_values: dict = meta.get("reference_values", {})
        self.sklearn_version_mismatch: str | None = None
        trained_version = meta.get("sklearn_version")
        if trained_version and trained_version != sklearn.__version__:
            self.sklearn_version_mismatch = (
                f"trained with scikit-learn {trained_version}, running {sklearn.__version__}"
            )

    def predict(self, row: dict) -> dict:
        """row keys are the EXACT dataset column names from meta['features']."""
        df = pd.DataFrame([{f: row[f] for f in self.features}])
        proba = float(self.pipeline.predict_proba(df)[:, 1][0])
        return {"probability": proba, "drivers": self._drivers(df, proba)}

    def _drivers(self, df: pd.DataFrame, base_proba: float) -> list[dict]:
        drivers = []
        for feature in self.features:
            if feature not in self.reference_values:
                continue
            df_ref = df.copy()
            df_ref[feature] = self.reference_values[feature]
            ref_proba = float(self.pipeline.predict_proba(df_ref)[:, 1][0])
            drop = base_proba - ref_proba  # positive => this value raises risk vs reference
            drivers.append({
                "name": feature,
                "value": df[feature].iloc[0],
                "contribution": drop,
                "direction": "up" if drop > 0 else "down",
            })
        drivers.sort(key=lambda d: abs(d["contribution"]), reverse=True)
        return drivers[:3]
