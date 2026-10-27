"""
Phase 2 step 5: POSTs every demo case in public/demo/demo_cases.json to a running
backend's real /analyze endpoint (never mocked/simulated) and prints each condition's
level + score vs threshold, the diabetes strategyUsed, and the narrative headline and
per-condition lines. Fails loudly (non-zero exit) on any safety-rule violation:

  (a) a not-assessed condition is shown as low/negative
  (b) a forbidden word (diagnosed/confirmed/cleared) appears anywhere in the narrative
  (c) the "N of 5 not assessed" count in fusion.note is wrong
  (d) TB or malaria is assessed without its image having been submitted
  (e) leukemia is ever assessed (no leukemia model loaded in this environment)
  (f) the diabetes narrative line does not say which model was used
  (g) with complete diabetes inputs, anything other than the combined model
      contributes to the diabetes fused score

Usage (backend already running, e.g. `uvicorn app.main:app --port 8001`):
    python scripts/smoke_real.py --base-url http://127.0.0.1:8001 --cases ../public/demo/demo_cases.json
"""
import argparse
import json
import sys
from pathlib import Path

import httpx

FORBIDDEN_WORDS = ["diagnosed", "diagnosis confirmed", "confirmed", "cleared"]
ALL_CONDITIONS = ["diabetes", "hypertension", "malaria", "leukemia", "tuberculosis"]

BACKEND_DIR = Path(__file__).resolve().parent.parent


def load_cases(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def build_clinical_lab_form(case: dict) -> dict:
    form = {}
    clinical = case.get("clinical")
    if clinical:
        if "age" in clinical:
            form["age"] = clinical["age"]
        if "sex" in clinical:
            form["sex"] = clinical["sex"]
        if "bmi" in clinical:
            form["bmi"] = clinical["bmi"]
        if "smokingHistory" in clinical:
            form["smoking_history"] = clinical["smokingHistory"]
        if "hypertension" in clinical:
            form["hypertension"] = str(clinical["hypertension"]).lower()
        if "heartDisease" in clinical:
            form["heart_disease"] = str(clinical["heartDisease"]).lower()
    lab = case.get("lab")
    if lab:
        if "hba1c" in lab:
            form["hba1c"] = lab["hba1c"]
        if "bloodGlucose" in lab:
            form["blood_glucose"] = lab["bloodGlucose"]
    return form


FILE_KEY_TO_FORM_FIELD = {
    "chestXray": "chest_xray",
    "smearCell": "smear_cell",
    "smearField": "smear_field",
    "ecg": "ecg",
}


def build_files(case: dict, repo_root: Path) -> dict:
    files = {}
    for key, form_field in FILE_KEY_TO_FORM_FIELD.items():
        url = case.get("files", {}).get(key)
        if not url:
            continue
        local_path = repo_root / "public" / url.lstrip("/")
        files[form_field] = (local_path.name, local_path.read_bytes(), "application/octet-stream")
    return files


def ensure_patient(client: httpx.Client, case: dict) -> str:
    patient = case["patient"]
    sex = patient["sex"] if patient["sex"] in ("male", "female", "other") else "other"
    resp = client.post("/patients", json={
        "mrn": f"DEMO-{case['id']}", "name": patient["name"], "age": patient["age"], "sex": sex,
    })
    resp.raise_for_status()
    return resp.json()["id"]


def check_case(case: dict, analysis: dict) -> list[str]:
    """Returns a list of violation strings (empty = all safety checks passed)."""
    violations = []
    fusion = analysis["fusion"]
    narrative = analysis["narrative"]
    full_text = narrative["headline"] + " " + " ".join(c["line"] for c in narrative["conditions"])

    # (a) not-assessed must never show as low/negative, and must never carry a score
    for c in fusion["perCondition"]:
        if c["condition"] not in fusion["assessedConditions"]:
            if c["riskLevel"] != "not_assessed":
                violations.append(f"(a) {case['id']}: {c['condition']} is not assessed but riskLevel={c['riskLevel']}")
            if c["fusedScore"]:
                violations.append(f"(a) {case['id']}: {c['condition']} is not assessed but has a nonzero fusedScore")

    # (b) forbidden words
    lowered = full_text.lower()
    for word in FORBIDDEN_WORDS:
        if word in lowered:
            violations.append(f"(b) {case['id']}: forbidden word '{word}' found in narrative")

    # (c) "N of 5 not assessed" count correctness
    n_assessed = len(fusion["assessedConditions"])
    n_not = len(fusion["notAssessedConditions"])
    if n_assessed + n_not != len(ALL_CONDITIONS):
        violations.append(f"(c) {case['id']}: assessed({n_assessed}) + notAssessed({n_not}) != 5")
    if f"{n_assessed} of {len(ALL_CONDITIONS)}" not in fusion["note"]:
        violations.append(f"(c) {case['id']}: fusion.note does not match assessed count: {fusion['note']!r}")

    # (d) TB/malaria must never be assessed without their image
    has_xray = bool(case.get("files", {}).get("chestXray"))
    has_cell = bool(case.get("files", {}).get("smearCell"))
    if "tuberculosis" in fusion["assessedConditions"] and not has_xray:
        violations.append(f"(d) {case['id']}: tuberculosis assessed without a chest X-ray submitted")
    if "malaria" in fusion["assessedConditions"] and not has_cell:
        violations.append(f"(d) {case['id']}: malaria assessed without a blood smear submitted")

    # (e) leukemia must never be assessed (no model loaded)
    if "leukemia" in fusion["assessedConditions"]:
        violations.append(f"(e) {case['id']}: leukemia was assessed, but no leukemia model is loaded")

    # (f) diabetes narrative line must say which model was used
    diabetes_line = next((c["line"] for c in narrative["conditions"] if c["condition"] == "diabetes"), None)
    if diabetes_line is not None and "Used:" not in diabetes_line:
        violations.append(f"(f) {case['id']}: diabetes narrative line missing 'Used: ...': {diabetes_line!r}")

    # (g) complete diabetes inputs -> only the combined model contributes
    diabetes_result = next((c for c in fusion["perCondition"] if c["condition"] == "diabetes"), None)
    has_complete_diabetes_inputs = bool(case.get("clinical")) and bool(case.get("lab"))
    if diabetes_result and has_complete_diabetes_inputs and diabetes_result["riskLevel"] != "not_assessed":
        contributing_modalities = {c["modality"] for c in diabetes_result["contributions"]}
        if contributing_modalities != {"clinicalLab"}:
            violations.append(f"(g) {case['id']}: complete diabetes inputs but contributions are "
                               f"{contributing_modalities}, not just the combined model")

    # Extra: a real high result must never be hidden, even with other inputs missing.
    for c in fusion["perCondition"]:
        if c["riskLevel"] == "high" and c["condition"] not in fusion["assessedConditions"]:
            violations.append(f"EXTRA {case['id']}: {c['condition']} is high but missing from assessedConditions")

    return violations


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8001")
    ap.add_argument("--cases", default=str(BACKEND_DIR.parent / "public" / "demo" / "demo_cases.json"))
    ap.add_argument("--save-replays", action="store_true",
                     help="Save each case's analysis to public/demo/replays/<id>.json")
    args = ap.parse_args()

    repo_root = BACKEND_DIR.parent
    cases_path = Path(args.cases)
    cases = load_cases(cases_path)

    client = httpx.Client(base_url=args.base_url, timeout=30)
    health = client.get("/health").json()
    print(f"Backend {args.base_url}: {len(health['models'])} models in /health\n")

    all_violations = []
    for case in cases:
        patient_id = ensure_patient(client, case)
        form = build_clinical_lab_form(case)
        form["patient_id"] = patient_id
        files = build_files(case, repo_root)

        resp = client.post("/analyze", data=form, files=files if files else None)
        resp.raise_for_status()
        analysis = resp.json()

        print(f"=== {case['title']} ===")
        for c in analysis["fusion"]["perCondition"]:
            extra = f" strategyUsed={c.get('strategyUsed')}" if c["condition"] == "diabetes" else ""
            thr = c.get("fusedThreshold")
            print(f"  {c['condition']:<14} level={c['riskLevel']:<13} score={c['fusedScore']:.4f} "
                  f"threshold={thr}{extra}")
        print(f"  headline: {analysis['narrative']['headline']}")
        for nc in analysis["narrative"]["conditions"]:
            print(f"    - [{nc['condition']}] {nc['line']}")

        violations = check_case(case, analysis)
        if violations:
            all_violations.extend(violations)
            print("  ** VIOLATIONS **")
            for v in violations:
                print(f"    ! {v}")
        else:
            print("  all safety checks passed")

        if args.save_replays:
            # Matches src/features/replay.ts's ReplayRecord contract exactly:
            # {recordedAt, fake, modelVersions, analysis} - never the Analysis object
            # flattened at top level.
            replay_dir = repo_root / "public" / "demo" / "replays"
            replay_dir.mkdir(parents=True, exist_ok=True)
            replay = {
                "recordedAt": analysis.get("createdAt"),
                "fake": any(m.get("simulatedOrFake") for m in health["models"]),
                "modelVersions": {m["id"]: str(m.get("testAuc")) for m in health["models"]},
                "analysis": analysis,
            }
            (replay_dir / f"{case['id']}.json").write_text(json.dumps(replay, indent=2))
        print()

    if all_violations:
        print(f"FAILED: {len(all_violations)} safety violation(s) found")
        sys.exit(1)
    print("All demo cases passed every safety check.")


if __name__ == "__main__":
    main()
