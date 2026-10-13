def test_empty_submission_is_422(client, patient_id):
    resp = client.post("/analyze", data={"patient_id": patient_id})
    assert resp.status_code == 422


def test_unknown_patient_is_404(client):
    resp = client.post("/analyze", data={"patient_id": "no-such-patient", "hba1c": "6.0", "blood_glucose": "100"})
    assert resp.status_code == 404


def test_out_of_range_value_is_422_and_names_the_field(client, patient_id):
    resp = client.post("/analyze", data={"patient_id": patient_id, "hba1c": "99", "blood_glucose": "100"})
    assert resp.status_code == 422
    assert "hba1c" in resp.json()["detail"]


def test_lab_only_assesses_diabetes_and_leaves_the_rest_not_assessed(client, patient_id):
    resp = client.post("/analyze", data={"patient_id": patient_id, "hba1c": "7.5", "blood_glucose": "180"})
    assert resp.status_code == 200
    body = resp.json()

    fusion = body["fusion"]
    assert "diabetes" in fusion["assessedConditions"]
    for condition in ("hypertension", "malaria", "leukemia", "tuberculosis"):
        assert condition in fusion["notAssessedConditions"]
        result = next(c for c in fusion["perCondition"] if c["condition"] == condition)
        assert result["riskLevel"] == "not_assessed"
        assert result["riskLevel"] != "low"

    assert fusion["overallRisk"] in ("low", "moderate", "high", "review_required")
    assert fusion["overallRisk"] != "incomplete_data"  # diabetes WAS assessed


def test_llm_is_off_by_default_even_if_requested(client, patient_id):
    resp = client.post(
        "/analyze",
        data={"patient_id": patient_id, "hba1c": "7.5", "blood_glucose": "180", "explain_with_llm": "true"},
    )
    assert resp.status_code == 200
    assert resp.json()["narrative"]["generatedBy"] == "template"


def test_fake_artifact_prefix_present_in_narrative(client, patient_id):
    resp = client.post("/analyze", data={"patient_id": patient_id, "hba1c": "7.5", "blood_glucose": "180"})
    assert resp.status_code == 200
    assert resp.json()["narrative"]["headline"].startswith("[TEST MODEL - NOT REAL]")
    assert resp.json()["uncertainty"]["modelStatus"] == "FAKE TEST ARTIFACT - numbers are meaningless"


def test_missing_clinical_field_does_not_run_that_model_and_lists_the_field(client, patient_id):
    # age/bmi provided but smoking_history/hypertension/heart_disease missing -> neither
    # clinical model has everything it needs, so 'clinical' modality is reported missing.
    resp = client.post("/analyze", data={"patient_id": patient_id, "age": "40", "bmi": "25"})
    assert resp.status_code == 200
    body = resp.json()
    clinical_input = next(i for i in body["inputs"] if i["type"] == "clinical")
    assert clinical_input["status"] == "missing"
    assert any("missing" in issue for issue in clinical_input["validation"]["issues"])


def test_zero_artifacts_app_starts_and_everything_is_not_assessed(tmp_path, no_artifacts_app_module):
    from fastapi.testclient import TestClient

    client = TestClient(no_artifacts_app_module.app)
    patient = client.post("/patients", json={"mrn": "MRN-2", "name": "P2", "age": 30, "sex": "male"}).json()
    resp = client.post("/analyze", data={"patient_id": patient["id"], "hba1c": "7.5", "blood_glucose": "180"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["fusion"]["overallRisk"] == "incomplete_data"
    assert len(body["fusion"]["notAssessedConditions"]) == 5
    lab_input = next(i for i in body["inputs"] if i["type"] == "lab")
    assert any("model not available" in issue for issue in lab_input["validation"]["issues"])
