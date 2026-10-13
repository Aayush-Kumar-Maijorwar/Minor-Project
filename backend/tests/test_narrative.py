from app.fusion import ModelRun, simulate_fusion
from app.narrative import FORBIDDEN_WORDS, build_narrative

CONFIG = {
    "diabetes": {"components": [{"modality": "lab", "weight": 0.5}, {"modality": "clinical", "weight": 0.5}],
                 "fused_threshold": 0.5},
    "hypertension": {"components": [{"modality": "clinical", "weight": 0.75}, {"modality": "ecg", "weight": 0.25}],
                      "fused_threshold": 0.5},
    "tuberculosis": {"components": [{"modality": "chestXray", "weight": 1.0}], "fused_threshold": 0.5},
    "malaria": {"components": [{"modality": "bloodSmearCell", "weight": 1.0}], "fused_threshold": 0.5},
    "leukemia": {"components": [{"modality": "bloodSmearField", "weight": 1.0}], "fused_threshold": 0.5},
}
MODEL_META = {
    "tb-resnet18": {"sensitivity": 0.95, "specificity": 0.88, "threshold": 0.42},
    "diabetes_lab": {"sensitivity": 0.9, "specificity": 0.8, "threshold": 0.31},
    "diabetes_clinical": {"sensitivity": 0.7, "specificity": 0.75, "threshold": 0.22},
}


def _all_text(narrative: dict) -> str:
    return " ".join([narrative["headline"], narrative["notAssessed"], narrative["disclaimer"]] +
                     [c["line"] for c in narrative["conditions"]])


def test_forbidden_words_never_appear():
    runs = [ModelRun(model_id="tb-resnet18", condition="tuberculosis", modality="chestXray", score=0.71, threshold=0.42)]
    fusion = simulate_fusion(runs, CONFIG, ["chestXray"])
    narrative = build_narrative(fusion, MODEL_META)
    text = _all_text(narrative).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in text
    assert "negative" not in text


def test_low_result_always_says_does_not_rule_out():
    runs = [ModelRun(model_id="tb-resnet18", condition="tuberculosis", modality="chestXray", score=0.05, threshold=0.42)]
    fusion = simulate_fusion(runs, CONFIG, ["chestXray"])
    narrative = build_narrative(fusion, MODEL_META)
    tb_line = next(c for c in narrative["conditions"] if c["condition"] == "tuberculosis")
    assert tb_line["level"] == "low"
    assert "does not rule out" in tb_line["line"]


def test_numbers_in_text_come_from_the_analysis_data():
    runs = [
        ModelRun(model_id="diabetes_lab", condition="diabetes", modality="lab", score=0.88, threshold=0.31),
        ModelRun(model_id="diabetes_clinical", condition="diabetes", modality="clinical", score=0.40, threshold=0.22),
    ]
    fusion = simulate_fusion(runs, CONFIG, ["lab", "clinical"])
    narrative = build_narrative(fusion, MODEL_META)
    diabetes_line = next(c for c in narrative["conditions"] if c["condition"] == "diabetes")["line"]
    assert "0.88" in diabetes_line
    assert "0.40" in diabetes_line
    assert "0.31" in diabetes_line
    assert "0.22" in diabetes_line


def test_fake_artifact_prefix():
    fusion = simulate_fusion([], CONFIG, [])
    narrative = build_narrative(fusion, {}, fake=True)
    assert narrative["headline"].startswith("[TEST MODEL - NOT REAL] ")


def test_headline_none_assessed_case():
    fusion = simulate_fusion([], CONFIG, [])
    narrative = build_narrative(fusion, {})
    assert narrative["priority"] == "incomplete"
    assert "no usable data" in narrative["headline"].lower()
