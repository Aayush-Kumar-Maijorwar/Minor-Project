from app.fusion import ModelRun, norm_score, simulate_fusion

BASIC_CONFIG = {
    "diabetes": {"components": [{"modality": "lab", "weight": 0.5}, {"modality": "clinical", "weight": 0.5}],
                 "fused_threshold": 0.5},
    "hypertension": {"components": [{"modality": "clinical", "weight": 0.75}, {"modality": "ecg", "weight": 0.25}],
                      "fused_threshold": 0.5},
    "tuberculosis": {"components": [{"modality": "chestXray", "weight": 1.0}], "fused_threshold": 0.5},
    "malaria": {"components": [{"modality": "bloodSmearCell", "weight": 1.0}], "fused_threshold": 0.5},
    "leukemia": {"components": [{"modality": "bloodSmearField", "weight": 1.0}], "fused_threshold": 0.5},
}


def test_norm_score_endpoints_and_midpoint():
    for t in (0.1, 0.3, 0.5, 0.7, 0.9):
        assert norm_score(0.0, t) == 0.0
        assert abs(norm_score(1.0, t) - 1.0) < 1e-9
        assert abs(norm_score(t, t) - 0.5) < 1e-9


def test_norm_score_is_monotone_in_p():
    t = 0.4
    scores = [norm_score(p, t) for p in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 0.9, 1.0]]
    assert scores == sorted(scores)


def test_single_model_path_equals_p_ge_t():
    for p, t in [(0.3, 0.4), (0.4, 0.4), (0.41, 0.4), (0.9, 0.2)]:
        runs = [ModelRun(model_id="tb-resnet18", condition="tuberculosis", modality="chestXray", score=p, threshold=t)]
        result = simulate_fusion(runs, BASIC_CONFIG, ["chestXray"])
        tb = next(c for c in result["perCondition"] if c["condition"] == "tuberculosis")
        assert (tb["riskLevel"] == "high") == (p >= t)


def test_weight_renormalisation_sums_to_one():
    runs = [
        ModelRun(model_id="diabetes_lab", condition="diabetes", modality="lab", score=0.6, threshold=0.3),
        ModelRun(model_id="diabetes_clinical", condition="diabetes", modality="clinical", score=0.2, threshold=0.2),
    ]
    result = simulate_fusion(runs, BASIC_CONFIG, ["lab", "clinical"])
    diabetes = next(c for c in result["perCondition"] if c["condition"] == "diabetes")
    assert abs(sum(c["weight"] for c in diabetes["contributions"]) - 1.0) < 1e-9


def test_a_missing_input_is_never_low_it_is_not_assessed():
    # Only lab provided: hypertension's only configured input besides clinical is ecg, so with
    # neither clinical nor ecg available, hypertension must be not_assessed - never 'low'.
    runs = [ModelRun(model_id="diabetes_lab", condition="diabetes", modality="lab", score=0.1, threshold=0.3)]
    result = simulate_fusion(runs, BASIC_CONFIG, ["lab"])
    hypertension = next(c for c in result["perCondition"] if c["condition"] == "hypertension")
    assert hypertension["riskLevel"] == "not_assessed"
    assert hypertension["riskLevel"] != "low"
    assert "hypertension" in result["notAssessedConditions"]


def test_b_a_lone_high_result_is_never_hidden():
    # Only a chest X-ray provided; TB model scores high. Overall must be 'high', not 'incomplete_data'.
    runs = [ModelRun(model_id="tb-resnet18", condition="tuberculosis", modality="chestXray", score=0.8, threshold=0.4)]
    result = simulate_fusion(runs, BASIC_CONFIG, ["chestXray"])
    tb = next(c for c in result["perCondition"] if c["condition"] == "tuberculosis")
    assert tb["riskLevel"] == "high"
    assert result["overallRisk"] == "high"
    assert result["overallRisk"] != "incomplete_data"


def test_c_nothing_assessed_is_incomplete_data():
    result = simulate_fusion([], BASIC_CONFIG, [])
    assert result["overallRisk"] == "incomplete_data"
    assert result["assessedConditions"] == []
    assert len(result["notAssessedConditions"]) == 5


def test_d_review_required_needs_high_and_extreme_raw_probability():
    runs_extreme = [ModelRun(model_id="tb-resnet18", condition="tuberculosis", modality="chestXray", score=0.95, threshold=0.4)]
    result = simulate_fusion(runs_extreme, BASIC_CONFIG, ["chestXray"])
    assert result["overallRisk"] == "review_required"

    runs_high_not_extreme = [ModelRun(model_id="tb-resnet18", condition="tuberculosis", modality="chestXray", score=0.7, threshold=0.4)]
    result2 = simulate_fusion(runs_high_not_extreme, BASIC_CONFIG, ["chestXray"])
    assert result2["overallRisk"] == "high"
    assert result2["overallRisk"] != "review_required"


def test_e_diabetes_fusion_json_overrides_default_weights():
    import json

    override_config = dict(BASIC_CONFIG)
    override_config["diabetes"] = {
        "components": [{"modality": "lab", "weight": 0.6}, {"modality": "clinical", "weight": 0.4}],
        "fused_threshold": 0.5,
    }
    runs = [
        ModelRun(model_id="diabetes_lab", condition="diabetes", modality="lab", score=0.9, threshold=0.5),
        ModelRun(model_id="diabetes_clinical", condition="diabetes", modality="clinical", score=0.1, threshold=0.5),
    ]
    result = simulate_fusion(runs, override_config, ["lab", "clinical"])
    diabetes = next(c for c in result["perCondition"] if c["condition"] == "diabetes")
    weights = {c["modality"]: c["weight"] for c in diabetes["contributions"]}
    assert abs(weights["lab"] - 0.6) < 1e-9
    assert abs(weights["clinical"] - 0.4) < 1e-9
