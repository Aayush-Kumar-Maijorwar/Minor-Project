"""
Ported from src/mock/engine/flags.ts - same reasons, same reason-string wording, same
per-condition rules. The only behavioural change from Phase 1 is upstream in fusion.py:
the review_required trigger is now "high AND a contributing raw probability >= 0.90"
instead of the Phase 1 demo's single-number threshold.
"""
import random
import string
from datetime import datetime, timezone

UPLOAD_HINTS = {
    "tuberculosis": "a chest X-ray",
    "malaria": "a blood smear",
    "leukemia": "a blood smear",
    "diabetes": "clinical or lab data",
    "hypertension": "clinical data or an ECG",
}


def _generate_flag_id() -> str:
    return "flag-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_flags(analysis_id: str, patient_id: str, fusion: dict) -> list[dict]:
    flags: list[dict] = []
    created_at = _now_iso()

    for result in fusion["perCondition"]:
        if result["riskLevel"] == "not_assessed":
            continue

        if result["riskLevel"] == "high":
            flags.append({
                "id": _generate_flag_id(),
                "patientId": patient_id,
                "analysisId": analysis_id,
                "condition": result["condition"],
                "severity": "high",
                "reason": f"{result['condition']} risk is high (fused score: {result['fusedScore']:.2f}).",
                "createdAt": created_at,
                "status": "open",
            })

        if result["fusedScore"] > 0.8:
            flags.append({
                "id": _generate_flag_id(),
                "patientId": patient_id,
                "analysisId": analysis_id,
                "condition": result["condition"],
                "severity": "review_required",
                "reason": (
                    f"{result['condition']} fused score {result['fusedScore']:.2f} exceeds the "
                    "review threshold. Clinical review required."
                ),
                "createdAt": created_at,
                "status": "open",
            })

    if fusion["notAssessedConditions"]:
        details = ", ".join(
            f"{c} (upload {UPLOAD_HINTS[c]})" for c in fusion["notAssessedConditions"]
        )
        flags.append({
            "id": _generate_flag_id(),
            "patientId": patient_id,
            "analysisId": analysis_id,
            "severity": "incomplete_data",
            "reason": f"Not assessed: {details}.",
            "createdAt": created_at,
            "status": "open",
        })

    return flags
