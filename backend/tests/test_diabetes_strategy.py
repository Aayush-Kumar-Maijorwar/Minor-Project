"""
Phase 1b step 5/8: the diabetes "best_available" strategy (config/fusion.json:
diabetes.strategy). When the combined lab+clinical model ran, it alone decides the
verdict - diabetes_lab/diabetes_clinical must never also be blended in (no
double-counting on the same underlying patient data). Otherwise, falls back to the
normal late fusion of whichever of lab/clinical actually ran.
"""
import json

import pytest

from app.fusion import ModelRun, norm_score, simulate_fusion
from app.narrative import build_narrative

DIABETES_CONFIG = {
    "diabetes": {
        "strategy": "best_available",
        "components": [{"modality": "lab", "weight": 0.5}, {"modality": "clinical", "weight": 0.5}],
        "fused_threshold": 0.5,
    }
}


def _run(model_id, modality, score, threshold=0.5):
    return ModelRun(model_id=model_id, condition="diabetes", modality=modality, score=score, threshold=threshold)


def test_strategy_combined_used_alone_when_all_inputs_present():
    runs = [
        _run("diabetes_combined", "clinicalLab", 0.80, 0.40),
        _run("diabetes_lab", "lab", 0.95, 0.30),       # would dominate a lab+clinical fusion if included
        _run("diabetes_clinical", "clinical", 0.10, 0.25),
    ]
    result = simulate_fusion(runs, DIABETES_CONFIG, ["lab", "clinical"])
    diabetes = next(c for c in result["perCondition"] if c["condition"] == "diabetes")

    assert diabetes["strategyUsed"] == "combined"
    assert len(diabetes["contributions"]) == 1
    assert diabetes["contributions"][0]["modality"] == "clinicalLab"
    assert set(diabetes["notUsedModelIds"]) == {"diabetes_lab", "diabetes_clinical"}


def test_no_double_counting_fused_score_matches_combined_alone():
    # If lab/clinical leaked into the average, fusedScore would differ from the
    # combined model's own norm_score - it must not.
    runs = [
        _run("diabetes_combined", "clinicalLab", 0.80, 0.40),
        _run("diabetes_lab", "lab", 0.01, 0.30),   # deliberately far from the combined score
        _run("diabetes_clinical", "clinical", 0.99, 0.25),
    ]
    result = simulate_fusion(runs, DIABETES_CONFIG, ["lab", "clinical"])
    diabetes = next(c for c in result["perCondition"] if c["condition"] == "diabetes")
    expected = norm_score(0.80, 0.40)
    assert abs(diabetes["fusedScore"] - expected) < 1e-9


def test_strategy_lab_only_when_clinical_did_not_run():
    runs = [_run("diabetes_lab", "lab", 0.7, 0.3)]
    result = simulate_fusion(runs, DIABETES_CONFIG, ["lab"])
    diabetes = next(c for c in result["perCondition"] if c["condition"] == "diabetes")
    assert diabetes["strategyUsed"] == "lab_only"
    assert len(diabetes["contributions"]) == 1
    assert abs(diabetes["fusedScore"] - norm_score(0.7, 0.3)) < 1e-9


def test_strategy_clinical_only_when_lab_did_not_run():
    runs = [_run("diabetes_clinical", "clinical", 0.6, 0.25)]
    result = simulate_fusion(runs, DIABETES_CONFIG, ["clinical"])
    diabetes = next(c for c in result["perCondition"] if c["condition"] == "diabetes")
    assert diabetes["strategyUsed"] == "clinical_only"


def test_strategy_fusion_when_lab_and_clinical_ran_but_not_combined():
    runs = [_run("diabetes_lab", "lab", 0.6, 0.3), _run("diabetes_clinical", "clinical", 0.4, 0.25)]
    result = simulate_fusion(runs, DIABETES_CONFIG, ["lab", "clinical"])
    diabetes = next(c for c in result["perCondition"] if c["condition"] == "diabetes")
    assert diabetes["strategyUsed"] == "fusion"
    assert len(diabetes["contributions"]) == 2
    assert abs(sum(c["weight"] for c in diabetes["contributions"]) - 1.0) < 1e-9


def test_strategy_none_ran_is_not_assessed():
    result = simulate_fusion([], DIABETES_CONFIG, [])
    diabetes = next(c for c in result["perCondition"] if c["condition"] == "diabetes")
    assert diabetes["riskLevel"] == "not_assessed"
    assert "strategyUsed" not in diabetes or diabetes.get("strategyUsed") is None


def test_threshold_decision_matches_the_combined_models_own_threshold():
    # Exactly at the combined model's own threshold -> norm_score is exactly 0.5 -> high
    runs = [_run("diabetes_combined", "clinicalLab", 0.40, 0.40)]
    result = simulate_fusion(runs, DIABETES_CONFIG, [])
    diabetes = next(c for c in result["perCondition"] if c["condition"] == "diabetes")
    assert diabetes["riskLevel"] == "high"

    runs_below = [_run("diabetes_combined", "clinicalLab", 0.39, 0.40)]
    result_below = simulate_fusion(runs_below, DIABETES_CONFIG, [])
    diabetes_below = next(c for c in result_below["perCondition"] if c["condition"] == "diabetes")
    assert diabetes_below["riskLevel"] != "high"


def test_narrative_says_combined_model_used():
    runs = [
        _run("diabetes_combined", "clinicalLab", 0.80, 0.40),
        _run("diabetes_lab", "lab", 0.5, 0.3),
        _run("diabetes_clinical", "clinical", 0.5, 0.25),
    ]
    fusion = simulate_fusion(runs, DIABETES_CONFIG, ["lab", "clinical"])
    narrative = build_narrative(fusion, {})
    line = next(c["line"] for c in narrative["conditions"] if c["condition"] == "diabetes")
    assert "Used: combined lab + clinical model." in line


def test_narrative_says_lab_model_only_when_clinical_incomplete():
    runs = [_run("diabetes_lab", "lab", 0.7, 0.3)]
    fusion = simulate_fusion(runs, DIABETES_CONFIG, ["lab"])
    narrative = build_narrative(fusion, {})
    line = next(c["line"] for c in narrative["conditions"] if c["condition"] == "diabetes")
    assert "Used: lab model only (clinical data incomplete)." in line


def test_narrative_says_clinical_model_only_when_lab_incomplete():
    runs = [_run("diabetes_clinical", "clinical", 0.6, 0.25)]
    fusion = simulate_fusion(runs, DIABETES_CONFIG, ["clinical"])
    narrative = build_narrative(fusion, {})
    line = next(c["line"] for c in narrative["conditions"] if c["condition"] == "diabetes")
    assert "Used: clinical model only (lab data incomplete)." in line


def test_uncertainty_message_for_clinical_only_diabetes():
    from app.uncertainty import build_uncertainty

    runs = [_run("diabetes_clinical", "clinical", 0.6, 0.25)]
    fusion = simulate_fusion(runs, DIABETES_CONFIG, ["clinical"])
    result = build_uncertainty([{"status": "ok", "confidence": 0.7}], fusion, DIABETES_CONFIG)
    assert any("based on clinical data only: low confidence" in m for m in result["messages"])


def test_loading_a_simple_format_tabular_checkpoint(tmp_path):
    """scripts/verify_diabetes_model.py-style comparison.json: a top-level test_auc/
    test_metrics, no results[]/selected wrapper - the registry's quality gate and
    narrative metadata lookup must still work against this shape."""
    import joblib
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    pipe = Pipeline([("scale", StandardScaler()), ("m", LogisticRegression())])
    X = np.array([[1.0], [2.0], [3.0], [4.0]])
    y = np.array([0, 0, 1, 1])
    pipe.fit(X, y)

    artifacts = tmp_path / "artifacts"
    (artifacts / "tabular").mkdir(parents=True)
    joblib.dump(pipe, artifacts / "tabular" / "diabetes_combined_best.joblib")
    meta = {
        "model_id": "diabetes_combined", "features": ["HbA1c_level"], "threshold": 0.5,
        "test_auc": 0.93, "test_metrics": {"sens": 0.95, "spec": 0.88, "FN": 3, "FP": 10},
        "sklearn_version": "1.9.1", "source": "user-trained (train_diabetes.py)",
    }
    (artifacts / "tabular" / "diabetes_combined_comparison.json").write_text(json.dumps(meta))

    from app.registry import Registry
    from pathlib import Path as _Path
    backend_dir = _Path(__file__).resolve().parent.parent
    registry = Registry(artifacts, backend_dir / "config", min_test_auc=0.65)

    slot = registry.slots["diabetes_combined"]
    assert slot.state == "loaded"
    tuned = registry._tuned_metrics(slot)
    assert tuned["sensitivity"] == 0.95
    assert tuned["specificity"] == 0.88
    health = next(m for m in registry.health_models() if m["id"] == "diabetes_combined")
    assert health["source"] == "user-trained (train_diabetes.py)"
    assert health["testAuc"] == 0.93
