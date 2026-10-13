"""
Generate tiny fake artifacts for local development and tests - NEVER real predictions.
Every comparison.json this writes has "fake": true, which the registry surfaces as
simulatedOrFake=true in /health, ModelPrediction.simulated=true, and the narrative
prefixes "[TEST MODEL - NOT REAL] ".

Usage (from backend/):
    python scripts/make_fake_artifacts.py --out artifacts_fake
"""
import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so `import app...` works run from anywhere

TABULAR_TASKS = {
    "diabetes_lab": dict(cat=[], num=["HbA1c_level", "blood_glucose_level"]),
    "diabetes_clinical": dict(cat=["gender", "smoking_history"], num=["age", "bmi", "hypertension", "heart_disease"]),
    "hypertension_clinical": dict(cat=["gender", "smoking_history"], num=["age", "bmi", "heart_disease"]),
}


def _fake_metrics():
    return {"threshold": 0.5, "sensitivity": 0.8, "specificity": 0.75, "precision": 0.6,
            "accuracy": 0.77, "f1": 0.68, "tp": 40, "fp": 10, "tn": 30, "fn": 10}


def _synthetic_df(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "gender": rng.choice(["Male", "Female"], n),
        "smoking_history": rng.choice(["never", "former", "current", "No Info"], n),
        "age": rng.uniform(18, 90, n),
        "bmi": rng.uniform(15, 45, n),
        "hypertension": rng.integers(0, 2, n),
        "heart_disease": rng.integers(0, 2, n),
        "HbA1c_level": rng.uniform(4, 10, n),
        "blood_glucose_level": rng.uniform(70, 300, n),
    })


def make_tabular(out_dir: Path, seed: int = 0):
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    df = _synthetic_df(200, seed)
    y = rng.integers(0, 2, len(df))

    for task, cfg in TABULAR_TASKS.items():
        cols = cfg["cat"] + cfg["num"]
        steps = [("n", StandardScaler(), cfg["num"])]
        if cfg["cat"]:
            steps.insert(0, ("c", OneHotEncoder(handle_unknown="ignore"), cfg["cat"]))
        pipe = Pipeline([("pre", ColumnTransformer(steps)), ("m", LogisticRegression(max_iter=200))])
        pipe.fit(df[cols], y)
        joblib.dump(pipe, out_dir / f"{task}_best.joblib")

        reference_values = {
            c: (float(df[c].median()) if c in cfg["num"] else str(df[c].mode()[0])) for c in cols
        }
        meta = {
            "task": task, "features": cols, "categorical": cfg["cat"], "numeric": cfg["num"],
            "selected": "logistic_regression", "threshold": 0.5, "target_sensitivity": 0.95,
            "reference_values": reference_values, "sklearn_version": sklearn.__version__,
            "results": [{"model": "logistic_regression", "test_auc": 0.7, "tuned": _fake_metrics()}],
            "fake": True, "note": "FAKE TEST ARTIFACT for local development only.",
        }
        with open(out_dir / f"{task}_comparison.json", "w") as f:
            json.dump(meta, f, indent=2)

    fusion_override = {
        "components": [
            {"model_id": "diabetes_lab", "weight": 0.6},
            {"model_id": "diabetes_clinical", "weight": 0.4},
        ],
        "fused_threshold": 0.5,
        "fake": True,
    }
    with open(out_dir / "diabetes_fusion.json", "w") as f:
        json.dump(fusion_override, f, indent=2)


def make_image_and_ecg(artifacts_dir: Path):
    try:
        import torch
    except ImportError:
        print("torch not installed - skipping fake image/ECG checkpoints (tabular fake artifacts still written).")
        return

    from app.predictors.image import TinyTestCnn  # a few KB, not a real architecture - see image.py

    for disease, folder in (("tb", "tb"), ("malaria", "malaria"), ("leukemia", "leukemia")):
        out = artifacts_dir / folder
        out.mkdir(parents=True, exist_ok=True)
        arch = "tiny_test_cnn"
        model = TinyTestCnn()
        torch.save(
            dict(disease=disease, arch=arch, state_dict=model.state_dict(), img_size=32,
                 threshold=0.5, mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225],
                 classes=["negative", "positive"], metrics=_fake_metrics(), test_auc=0.7),
            out / f"{disease}_best.pt",
        )
        meta = {
            "disease": disease, "selected": arch,
            "results": [{"arch": arch, "test_auc": 0.7, "tuned": _fake_metrics()}],
            "fake": True, "note": "FAKE TEST ARTIFACT for local development only.",
        }
        with open(out / "comparison.json", "w") as f:
            json.dump(meta, f, indent=2)

    from app.predictors.ecg import Cnn1dSmall  # same arch the registry will rebuild on load

    out = artifacts_dir / "ecg"
    out.mkdir(parents=True, exist_ok=True)
    model = Cnn1dSmall()
    torch.save(
        dict(task="hypertension_ecg_screen", arch="cnn1d_small", state_dict=model.state_dict(),
             input_len=187, threshold=0.5, classes=["normal", "abnormal"],
             metrics=_fake_metrics(), test_auc=0.7),
        out / "ecg_best.pt",
    )
    meta = {
        "task": "hypertension_ecg_screen", "selected": "cnn1d_small",
        "results": [{"arch": "cnn1d_small", "test_auc": 0.7, "tuned": _fake_metrics()}],
        "fake": True, "note": "FAKE TEST ARTIFACT for local development only.",
    }
    with open(out / "comparison.json", "w") as f:
        json.dump(meta, f, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out_dir = Path(args.out)
    make_tabular(out_dir / "tabular")
    make_image_and_ecg(out_dir)
    print(f"Fake artifacts written to {out_dir}")


if __name__ == "__main__":
    main()
