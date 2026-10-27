from app.flags import build_flags
from app.fusion import ModelRun, simulate_fusion
from app.uncertainty import build_uncertainty

CONFIG = {
    "diabetes": {"components": [{"modality": "lab", "weight": 0.5}, {"modality": "clinical", "weight": 0.5}],
                 "fused_threshold": 0.5},
    "hypertension": {"components": [{"modality": "clinical", "weight": 0.75}, {"modality": "ecg", "weight": 0.25}],
                      "fused_threshold": 0.5},
    "tuberculosis": {"components": [{"modality": "chestXray", "weight": 1.0}], "fused_threshold": 0.5},
    "malaria": {"components": [{"modality": "bloodSmearCell", "weight": 1.0}], "fused_threshold": 0.5},
    "leukemia": {"components": [{"modality": "bloodSmearField", "weight": 1.0}], "fused_threshold": 0.5},
}


def test_high_condition_reason_wording_matches_ts_port():
    runs = [ModelRun(model_id="tb-resnet18", condition="tuberculosis", modality="chestXray", score=0.71, threshold=0.42)]
    fusion = simulate_fusion(runs, CONFIG, ["chestXray"])
    tb = next(c for c in fusion["perCondition"] if c["condition"] == "tuberculosis")
    flags = build_flags("AN-1", "PT-1", fusion)
    high_flag = next(f for f in flags if f["severity"] == "high")
    assert high_flag["reason"] == f"tuberculosis risk is high (fused score: {tb['fusedScore']:.2f})."
    assert high_flag["condition"] == "tuberculosis"


def test_incomplete_data_flag_lists_upload_hints():
    runs = [ModelRun(model_id="diabetes_lab", condition="diabetes", modality="lab", score=0.1, threshold=0.3)]
    fusion = simulate_fusion(runs, CONFIG, ["lab"])
    flags = build_flags("AN-1", "PT-1", fusion)
    incomplete = next(f for f in flags if f["severity"] == "incomplete_data")
    assert incomplete["reason"].startswith("Not assessed: ")
    assert "tuberculosis (upload a chest X-ray)" in incomplete["reason"]
    assert "hypertension (upload clinical data or an ECG)" in incomplete["reason"]


def test_review_required_flag_when_fused_score_exceeds_point_eight():
    runs = [ModelRun(model_id="tb-resnet18", condition="tuberculosis", modality="chestXray", score=0.95, threshold=0.3)]
    fusion = simulate_fusion(runs, CONFIG, ["chestXray"])
    flags = build_flags("AN-1", "PT-1", fusion)
    assert any(f["severity"] == "review_required" and f["condition"] == "tuberculosis" for f in flags)


def test_uncertainty_confidence_is_mean_of_ok_predictions():
    predictions = [
        {"status": "ok", "confidence": 0.8},
        {"status": "ok", "confidence": 0.6},
        {"status": "skipped_missing_input", "confidence": 0.0},
    ]
    fusion = simulate_fusion([], CONFIG, [])
    result = build_uncertainty(predictions, fusion, CONFIG)
    assert abs(result["confidence"] - 0.7) < 1e-9


def test_uncertainty_confidence_zero_with_no_predictions():
    fusion = simulate_fusion([], CONFIG, [])
    result = build_uncertainty([], fusion, CONFIG)
    assert result["confidence"] == 0.0


def test_uncertainty_notes_single_of_multiple_models_used():
    # hypertension has two possible components (clinical + ecg) but only clinical ran.
    runs = [ModelRun(model_id="hypertension_clinical", condition="hypertension", modality="clinical", score=0.2, threshold=0.3)]
    fusion = simulate_fusion(runs, CONFIG, ["clinical"])
    result = build_uncertainty([{"status": "ok", "confidence": 0.7}], fusion, CONFIG)
    assert any("hypertension: based on clinical only" in m for m in result["messages"])


def test_uncertainty_fake_model_status():
    fusion = simulate_fusion([], CONFIG, [])
    result = build_uncertainty([], fusion, CONFIG, fake=True)
    assert result["modelStatus"] == "FAKE TEST ARTIFACT - numbers are meaningless"
