"""
Phase 2 step 6: the partial-input proof against the REAL trained models (never fake
artifacts) - every combination of inputs produces exactly the right set of assessed
conditions, and the safety invariants hold: a missing/unusable input is always
not_assessed (never low/negative, never carries a score), and a real high result is
never hidden just because some other input is missing.

Skipped automatically if the real model binaries (.pt/.joblib, gitignored) aren't
present in backend/artifacts/ - this test exercises the actual trained weights, not
the synthetic fake-artifact fixture the rest of the suite uses.
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from tests.conftest import _fresh_app_module  # noqa: E402

REAL_ARTIFACTS = BACKEND_DIR / "artifacts"
_REQUIRED_REAL_FILES = [
    REAL_ARTIFACTS / "tb" / "tb_best.pt",
    REAL_ARTIFACTS / "malaria" / "malaria_best.pt",
    REAL_ARTIFACTS / "tabular" / "diabetes_lab_best.joblib",
    REAL_ARTIFACTS / "tabular" / "diabetes_clinical_best.joblib",
    REAL_ARTIFACTS / "tabular" / "diabetes_combined_best.joblib",
    REAL_ARTIFACTS / "tabular" / "hypertension_clinical_best.joblib",
]
pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in _REQUIRED_REAL_FILES),
    reason="real model binaries not present (gitignored) - run training/copy real artifacts first",
)

TB_IMAGE = (REAL_ARTIFACTS / "tb" / "samples" / "tb_pos_1.png").read_bytes()
MALARIA_IMAGE = (REAL_ARTIFACTS / "malaria" / "samples" / "malaria_pos_1.png").read_bytes()

# A genuine photograph (not a fabricated placeholder) used ONLY for the "model
# missing" input-validation path below - no leukemia model is loaded, so nothing ever
# actually runs inference on it; it exists purely to exercise "an image was submitted
# but its model isn't available", not to pretend this is a real blood-smear-field case.
LEUKEMIA_FIELD_PLACEHOLDER_IMAGE = MALARIA_IMAGE

LAB_POSITIVE = {"hba1c": "9.0", "blood_glucose": "240"}
CLINICAL_POSITIVE = {
    "age": "60", "sex": "Male", "bmi": "32", "smoking_history": "former",
    "hypertension": "true", "heart_disease": "false",
}


@pytest.fixture()
def real_client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    module = _fresh_app_module(REAL_ARTIFACTS, tmp_path / "data", monkeypatch)
    return TestClient(module.app)


@pytest.fixture()
def real_patient_id(real_client) -> str:
    resp = real_client.post("/patients", json={"mrn": "REAL-1", "name": "Real Patient", "age": 55, "sex": "male"})
    assert resp.status_code == 200
    return resp.json()["id"]


def _assert_safety_invariants(fusion: dict):
    for c in fusion["perCondition"]:
        if c["condition"] not in fusion["assessedConditions"]:
            assert c["riskLevel"] == "not_assessed", f"{c['condition']} not assessed but riskLevel={c['riskLevel']}"
            assert not c["fusedScore"], f"{c['condition']} not assessed but has a score"
    # A real high result is never hidden just because other inputs are missing.
    for c in fusion["perCondition"]:
        if c["riskLevel"] == "high":
            assert c["condition"] in fusion["assessedConditions"]


def test_chest_xray_only_assesses_only_tuberculosis(real_client, real_patient_id):
    resp = real_client.post("/analyze", data={"patient_id": real_patient_id},
                             files={"chest_xray": ("tb.png", TB_IMAGE, "image/png")})
    assert resp.status_code == 200
    fusion = resp.json()["fusion"]
    assert fusion["assessedConditions"] == ["tuberculosis"]
    _assert_safety_invariants(fusion)


def test_malaria_cell_only_assesses_only_malaria(real_client, real_patient_id):
    resp = real_client.post("/analyze", data={"patient_id": real_patient_id},
                             files={"smear_cell": ("malaria.png", MALARIA_IMAGE, "image/png")})
    assert resp.status_code == 200
    fusion = resp.json()["fusion"]
    assert fusion["assessedConditions"] == ["malaria"]
    _assert_safety_invariants(fusion)


def test_lab_only_assesses_diabetes_via_lab_model(real_client, real_patient_id):
    resp = real_client.post("/analyze", data={"patient_id": real_patient_id, **LAB_POSITIVE})
    assert resp.status_code == 200
    body = resp.json()
    fusion = body["fusion"]
    assert fusion["assessedConditions"] == ["diabetes"]
    diabetes = next(c for c in fusion["perCondition"] if c["condition"] == "diabetes")
    assert diabetes["strategyUsed"] == "lab_only"
    _assert_safety_invariants(fusion)


def test_clinical_only_assesses_diabetes_low_confidence_and_hypertension(real_client, real_patient_id):
    resp = real_client.post("/analyze", data={"patient_id": real_patient_id, **CLINICAL_POSITIVE})
    assert resp.status_code == 200
    body = resp.json()
    fusion = body["fusion"]
    assert set(fusion["assessedConditions"]) == {"diabetes", "hypertension"}
    diabetes = next(c for c in fusion["perCondition"] if c["condition"] == "diabetes")
    assert diabetes["strategyUsed"] == "clinical_only"
    assert "based on clinical data only: low confidence" in body["uncertainty"]["messages"]
    _assert_safety_invariants(fusion)


def test_lab_and_clinical_assesses_diabetes_via_combined_and_hypertension(real_client, real_patient_id):
    resp = real_client.post("/analyze", data={"patient_id": real_patient_id, **LAB_POSITIVE, **CLINICAL_POSITIVE})
    assert resp.status_code == 200
    fusion = resp.json()["fusion"]
    assert set(fusion["assessedConditions"]) == {"diabetes", "hypertension"}
    diabetes = next(c for c in fusion["perCondition"] if c["condition"] == "diabetes")
    assert diabetes["strategyUsed"] == "combined"
    assert {c["modality"] for c in diabetes["contributions"]} == {"clinicalLab"}
    _assert_safety_invariants(fusion)


def test_xray_and_lab_assesses_tb_and_diabetes_lab_only_rest_not_assessed(real_client, real_patient_id):
    resp = real_client.post("/analyze", data={"patient_id": real_patient_id, **LAB_POSITIVE},
                             files={"chest_xray": ("tb.png", TB_IMAGE, "image/png")})
    assert resp.status_code == 200
    fusion = resp.json()["fusion"]
    assert set(fusion["assessedConditions"]) == {"tuberculosis", "diabetes"}
    for condition in ("malaria", "leukemia", "hypertension"):
        assert condition in fusion["notAssessedConditions"]
    diabetes = next(c for c in fusion["perCondition"] if c["condition"] == "diabetes")
    assert diabetes["strategyUsed"] == "lab_only"
    _assert_safety_invariants(fusion)


def test_all_real_modalities_assesses_everything_but_leukemia(real_client, real_patient_id):
    resp = real_client.post(
        "/analyze",
        data={"patient_id": real_patient_id, **LAB_POSITIVE, **CLINICAL_POSITIVE},
        files={
            "chest_xray": ("tb.png", TB_IMAGE, "image/png"),
            "smear_cell": ("malaria.png", MALARIA_IMAGE, "image/png"),
        },
    )
    assert resp.status_code == 200
    fusion = resp.json()["fusion"]
    assert set(fusion["assessedConditions"]) == {"tuberculosis", "malaria", "diabetes", "hypertension"}
    assert fusion["notAssessedConditions"] == ["leukemia"]
    _assert_safety_invariants(fusion)


def test_hba1c_without_glucose_is_not_assessed_and_names_the_field(real_client, real_patient_id):
    resp = real_client.post("/analyze", data={"patient_id": real_patient_id, "hba1c": "7.0"})
    assert resp.status_code == 200
    body = resp.json()
    fusion = body["fusion"]
    assert "diabetes" in fusion["notAssessedConditions"]
    lab_input = next(i for i in body["inputs"] if i["type"] == "lab")
    assert any("blood_glucose" in issue for issue in lab_input["validation"]["issues"])
    _assert_safety_invariants(fusion)


def test_leukemia_field_image_only_no_crash_all_not_assessed(real_client, real_patient_id):
    resp = real_client.post(
        "/analyze", data={"patient_id": real_patient_id},
        files={"smear_field": ("field.png", LEUKEMIA_FIELD_PLACEHOLDER_IMAGE, "image/png")},
    )
    assert resp.status_code == 200
    fusion = resp.json()["fusion"]
    assert fusion["assessedConditions"] == []
    assert fusion["overallRisk"] == "incomplete_data"
    _assert_safety_invariants(fusion)


def test_no_inputs_is_422(real_client, real_patient_id):
    resp = real_client.post("/analyze", data={"patient_id": real_patient_id})
    assert resp.status_code == 422
    assert "Provide at least one input" in resp.json()["detail"]
