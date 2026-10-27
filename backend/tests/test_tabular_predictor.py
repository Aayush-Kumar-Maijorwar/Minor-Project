import json
from pathlib import Path

from app.predictors.tabular import TabularPredictor


def test_top3_drivers_ranked_by_absolute_drop(fake_artifacts_dir):
    folder = fake_artifacts_dir / "tabular"
    meta = json.loads((folder / "diabetes_clinical_comparison.json").read_text())
    predictor = TabularPredictor(folder / "diabetes_clinical_best.joblib", meta)

    row = {"gender": "Female", "smoking_history": "never", "age": 55, "bmi": 32, "hypertension": 1, "heart_disease": 0}
    result = predictor.predict(row)

    assert 0.0 <= result["probability"] <= 1.0
    assert len(result["drivers"]) <= 3
    drops = [abs(d["contribution"]) for d in result["drivers"]]
    assert drops == sorted(drops, reverse=True)
    for d in result["drivers"]:
        assert d["direction"] in ("up", "down")
        assert d["name"] in predictor.features
