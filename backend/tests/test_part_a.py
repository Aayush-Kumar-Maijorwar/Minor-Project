"""Phase 3 Part A: submittedValues, POST /analyses/{id}/narrative, /models URLs."""


def test_submitted_values_are_numbers_and_enums_only(client, patient_id):
    resp = client.post(
        "/analyze",
        data={"patient_id": patient_id, "hba1c": "7.5", "blood_glucose": "180",
              "age": "55", "sex": "Female", "bmi": "31", "smoking_history": "never",
              "hypertension": "false", "heart_disease": "false"},
    )
    assert resp.status_code == 200
    submitted = resp.json()["submittedValues"]
    assert submitted["lab"] == {"hba1c": 7.5, "blood_glucose": 180.0}
    assert submitted["clinical"] is not None
    assert "age" in str(submitted["clinical"])


def test_submitted_values_is_null_for_unused_sections(client, patient_id):
    resp = client.post("/analyze", data={"patient_id": patient_id, "hba1c": "7.5", "blood_glucose": "180"})
    assert resp.status_code == 200
    submitted = resp.json()["submittedValues"]
    assert submitted["clinical"] is None
    assert submitted["lab"] is not None


def test_narrative_endpoint_returns_template_by_default_without_rerunning_models(client, patient_id):
    analyze_resp = client.post("/analyze", data={"patient_id": patient_id, "hba1c": "7.5", "blood_glucose": "180"})
    analysis = analyze_resp.json()
    analysis_id = analysis["id"]

    resp = client.post(f"/analyses/{analysis_id}/narrative", json={"llm": False})
    assert resp.status_code == 200
    narrative = resp.json()
    assert narrative["generatedBy"] == "template"
    assert narrative["headline"] == analysis["narrative"]["headline"]

    # The stored analysis is untouched - confirms no model rerun / no mutation.
    stored = client.get(f"/analyses/{analysis_id}").json()
    assert stored["narrative"]["headline"] == analysis["narrative"]["headline"]


def test_narrative_endpoint_llm_requires_server_flag_and_falls_back(client, patient_id):
    analyze_resp = client.post("/analyze", data={"patient_id": patient_id, "hba1c": "7.5", "blood_glucose": "180"})
    analysis_id = analyze_resp.json()["id"]

    # NARRATIVE_LLM=0 in the test fixture -> llm=true still falls back to template.
    resp = client.post(f"/analyses/{analysis_id}/narrative", json={"llm": True})
    assert resp.status_code == 200
    assert resp.json()["generatedBy"] == "template"


def test_narrative_endpoint_404_for_unknown_analysis(client):
    resp = client.post("/analyses/no-such-id/narrative", json={"llm": False})
    assert resp.status_code == 404


def test_models_include_comparison_and_fusion_urls_and_fake_flag(client):
    resp = client.get("/models")
    assert resp.status_code == 200
    models = resp.json()
    assert len(models) == 8

    for m in models:
        assert m["fake"] is True  # fixture uses fake artifacts throughout
        assert m["comparisonUrl"] is not None
        assert m["comparisonUrl"].startswith("/static/artifacts/")

    diabetes_models = [m for m in models if m["condition"] == "diabetes"]
    assert diabetes_models
    for m in diabetes_models:
        assert m["fusionUrl"] == "/static/artifacts/tabular/diabetes_fusion.json"

    non_diabetes = [m for m in models if m["condition"] != "diabetes"]
    assert all(m["fusionUrl"] is None for m in non_diabetes)
