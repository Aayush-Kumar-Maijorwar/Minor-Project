"""
Phase 2 step 6: prints a table of assessed vs not-assessed conditions for every
input combination, against a running backend's real /analyze endpoint. The same
combinations and expected outcomes are asserted for real in
backend/tests/test_partial_inputs.py - this script is the human-readable report.

Usage (backend already running, e.g. `uvicorn app.main:app --port 8001`):
    python scripts/partial_inputs_matrix.py --base-url http://127.0.0.1:8001
"""
import argparse
import sys
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parent.parent
ALL_CONDITIONS = ["diabetes", "hypertension", "malaria", "leukemia", "tuberculosis"]

LAB_POSITIVE = {"hba1c": "9.0", "blood_glucose": "240"}
CLINICAL_POSITIVE = {
    "age": "60", "sex": "Male", "bmi": "32", "smoking_history": "former",
    "hypertension": "true", "heart_disease": "false",
}

COMBINATIONS = [
    ("chest X-ray only", {}, ["chest_xray"]),
    ("malaria cell only", {}, ["smear_cell"]),
    ("lab only", LAB_POSITIVE, []),
    ("clinical only", CLINICAL_POSITIVE, []),
    ("lab + clinical", {**LAB_POSITIVE, **CLINICAL_POSITIVE}, []),
    ("X-ray + lab", LAB_POSITIVE, ["chest_xray"]),
    ("X-ray + malaria cell + lab + clinical", {**LAB_POSITIVE, **CLINICAL_POSITIVE}, ["chest_xray", "smear_cell"]),
    ("HbA1c without glucose", {"hba1c": "7.0"}, []),
    ("leukemia field image only", {}, ["smear_field"]),
    ("no inputs", {}, []),
]


def load_sample_bytes():
    tb = (BACKEND_DIR / "artifacts" / "tb" / "samples" / "tb_pos_1.png").read_bytes()
    malaria = (BACKEND_DIR / "artifacts" / "malaria" / "samples" / "malaria_pos_1.png").read_bytes()
    return {"chest_xray": ("tb.png", tb, "image/png"),
            "smear_cell": ("malaria.png", malaria, "image/png"),
            "smear_field": ("field.png", malaria, "image/png")}  # no leukemia model loaded; never run on this


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8001")
    args = ap.parse_args()

    client = httpx.Client(base_url=args.base_url, timeout=30)
    resp = client.post("/patients", json={"mrn": "MATRIX-1", "name": "Matrix Patient", "age": 55, "sex": "male"})
    resp.raise_for_status()
    patient_id = resp.json()["id"]

    sample_files = load_sample_bytes()

    print(f"{'combination':<42} {'status':<6} {'assessed':<45} not_assessed")
    all_ok = True
    for label, form, file_keys in COMBINATIONS:
        data = {"patient_id": patient_id, **form}
        files = {k: sample_files[k] for k in file_keys} if file_keys else None
        resp = client.post("/analyze", data=data, files=files)

        if resp.status_code != 200:
            print(f"{label:<42} {resp.status_code:<6} {resp.json().get('detail', '')}")
            continue

        fusion = resp.json()["fusion"]
        assessed = ", ".join(fusion["assessedConditions"]) or "(none)"
        not_assessed = ", ".join(fusion["notAssessedConditions"]) or "(none)"
        print(f"{label:<42} {resp.status_code:<6} {assessed:<45} {not_assessed}")

        for c in fusion["perCondition"]:
            if c["condition"] not in fusion["assessedConditions"] and c["riskLevel"] != "not_assessed":
                print(f"  ! VIOLATION: {c['condition']} not assessed but riskLevel={c['riskLevel']}")
                all_ok = False

    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
