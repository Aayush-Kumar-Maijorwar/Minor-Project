"""
Deterministic plain-English narrative, always on (section 6 of the Phase 2 spec).

Hard safety rules enforced here (see project README):
 - never says diagnosed / confirmed / cleared
 - never calls missing data "negative"
 - every low result carries "does not rule out"
 - fake-artifact runs are prefixed "[TEST MODEL - NOT REAL] "
"""

FORBIDDEN_WORDS = ["diagnose", "diagnosed", "confirm", "confirmed", "clear", "cleared", "negative"]

UPLOAD_HINTS = {
    "tuberculosis": "chest X-ray",
    "malaria": "blood smear",
    "leukemia": "blood smear",
    "diabetes": "clinical or lab data",
    "hypertension": "clinical data or ECG",
}

INPUT_LABELS = {
    "chestXray": "chest X-ray",
    "bloodSmearCell": "blood smear",
    "bloodSmearField": "blood smear",
    "ecg": "ECG",
    "clinical": "clinical data",
    "lab": "lab result",
    "clinicalLab": "combined lab + clinical data",
}

MODEL_LABELS = {
    "chestXray": "chest X-ray",
    "bloodSmearCell": "blood smear",
    "bloodSmearField": "blood smear",
    "ecg": "ECG",
    "clinical": "clinical",
    "lab": "lab",
    "clinicalLab": "combined",
}

DIABETES_STRATEGY_SUFFIX = {
    "combined": " Used: combined lab + clinical model.",
    "fusion": " Used: lab + clinical models (fused).",
    "lab_only": " Used: lab model only (clinical data incomplete).",
    "clinical_only": " Used: clinical model only (lab data incomplete).",
}

DISCLAIMER = (
    "Decision support from models trained on public datasets; not a diagnosis and not "
    "clinically validated."
)

HBA1C_FEATURE_NAMES = {"HbA1c_level", "hba1c"}
BMI_FEATURE_NAMES = {"bmi"}


def _title(condition: str) -> str:
    return condition[0].upper() + condition[1:]


def _pct(x: float) -> str:
    return f"{round(x * 100)}%"


def _context_tag(name: str, value) -> str:
    if value is None:
        return ""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    if name in HBA1C_FEATURE_NAMES:
        if v >= 6.5:
            return ", in the diabetic range"
        if v >= 5.7:
            return ", in the prediabetes range"
    if name in BMI_FEATURE_NAMES and v >= 30:
        return ", in the obesity range"
    return ""


def _driver_text(contributions: list[dict], drivers_by_model: dict) -> str:
    for contrib in contributions:
        drivers = drivers_by_model.get(contrib["modelId"])
        if drivers:
            parts = []
            for d in drivers[:3]:
                direction = "raises risk" if d["direction"] == "up" else "lowers risk"
                value_txt = f" {d['value']}" if d.get("value") is not None else ""
                tag = _context_tag(d["name"], d.get("value"))
                parts.append(f"{d['name']}{value_txt} ({direction}{tag})")
            return " Main drivers: " + ", ".join(parts) + "."
    return ""


def _single_model_line(condition: str, result: dict, model_meta: dict, drivers_by_model: dict) -> str:
    contrib = result["contributions"][0]
    meta = model_meta.get(contrib["modelId"], {})
    sens, spec = meta.get("sensitivity"), meta.get("specificity")
    # Narrative numbers are the model's OWN raw probability/threshold (interpretable), not the
    # internal 0..1 fused/normalised scale fusion.py uses for the cross-model decision.
    score, t = contrib["score"], meta.get("threshold", 0.5)
    cname = _title(condition)
    input_label = INPUT_LABELS.get(contrib["modality"], contrib["modality"])

    if result["riskLevel"] == "high":
        perf = ""
        if sens is not None and spec is not None:
            perf = (
                f" On held-out public-dataset test data it caught about {_pct(sens)} of "
                f"{condition} cases, with about {_pct(1 - spec)} false alarms."
            )
        line = (
            f"{cname}: FLAGGED (score {score:.2f}, flag threshold {t:.2f}). The {input_label} "
            f"scores above the level this model flags for review.{perf} "
            "Screening support only; clinical correlation recommended."
        )
    elif result["riskLevel"] == "moderate":
        line = (
            f"{cname}: BORDERLINE (score {score:.2f}, flag threshold {t:.2f}). Close to the flag "
            "level; consider clinical correlation."
        )
    else:
        line = (
            f"{cname}: no indication on this {input_label} (score {score:.2f}, below flag "
            f"threshold {t:.2f}). This does not rule out {condition}."
        )

    line += _driver_text(result["contributions"], drivers_by_model)
    if condition == "hypertension" and contrib["modality"] == "ecg":
        line += (
            " ECG cardiac-abnormality screen (supporting evidence only, not a "
            "hypertension-specific test)."
        )
    return line


def _multi_model_line(condition: str, result: dict, model_meta: dict, drivers_by_model: dict) -> str:
    cname = _title(condition)
    fused, t = result["fusedScore"], result.get("fusedThreshold", 0.5)
    parts = []
    for contrib in result["contributions"]:
        meta = model_meta.get(contrib["modelId"], {})
        label = MODEL_LABELS.get(contrib["modality"], contrib["modality"])
        thr = meta.get("threshold", 0.0)
        parts.append(f"{label} model {contrib['score']:.2f} (threshold {thr:.2f})")
    weights_txt = "/".join(f"{round(c['weight'] * 100)}%" for c in result["contributions"])

    if result["riskLevel"] == "high":
        status = "FLAGGED"
    elif result["riskLevel"] == "moderate":
        status = "BORDERLINE"
    else:
        status = f"no indication (score {fused:.2f}, below flag threshold {t:.2f})"

    line = f"{cname}: {status}. {', '.join(parts)}; combined with weights {weights_txt}."
    line += _driver_text(result["contributions"], drivers_by_model)
    if result["riskLevel"] == "low":
        line += f" This does not rule out {condition}."
    if condition == "hypertension" and any(c["modality"] == "ecg" for c in result["contributions"]):
        line += (
            " ECG cardiac-abnormality screen (supporting evidence only, not a "
            "hypertension-specific test)."
        )
    return line


def _condition_line(result: dict, model_meta: dict, drivers_by_model: dict) -> str:
    condition = result["condition"]
    if len(result["contributions"]) == 1:
        line = _single_model_line(condition, result, model_meta, drivers_by_model)
    else:
        line = _multi_model_line(condition, result, model_meta, drivers_by_model)
    if condition == "diabetes":
        line += DIABETES_STRATEGY_SUFFIX.get(result.get("strategyUsed"), "")
    return line


def build_narrative(
    fusion: dict,
    model_meta: dict,
    drivers_by_model: dict | None = None,
    fake: bool = False,
) -> dict:
    """model_meta: {model_id: {"sensitivity":..,"specificity":..,"threshold":..}}
    drivers_by_model: {model_id: [{"name","value","direction","contribution"}]} (tabular only)
    """
    drivers_by_model = drivers_by_model or {}
    assessed = fusion["assessedConditions"]
    not_assessed = fusion["notAssessedConditions"]
    flagged = [c["condition"] for c in fusion["perCondition"] if c["riskLevel"] == "high"]

    if not assessed:
        headline = "No condition could be assessed: no usable data was provided."
        priority = "incomplete"
    elif flagged:
        names = ", ".join(_title(c) for c in flagged)
        headline = f"Priority: REVIEW. {names} flagged. {len(not_assessed)} of 5 conditions not assessed."
        priority = "review"
    else:
        headline = (
            f"No condition flagged on the data provided. {len(not_assessed)} of 5 not "
            "assessed; this does not rule out disease."
        )
        priority = "routine"

    conditions = []
    for result in fusion["perCondition"]:
        if result["riskLevel"] == "not_assessed":
            continue
        conditions.append({
            "condition": result["condition"],
            "level": result["riskLevel"],
            "line": _condition_line(result, model_meta, drivers_by_model),
        })

    not_assessed_text = ""
    if not_assessed:
        names = ", ".join(_title(c) for c in not_assessed)
        hints = ", ".join(UPLOAD_HINTS[c] for c in not_assessed)
        not_assessed_text = f"{names}: not assessed (no {hints} provided)."

    narrative = {
        "headline": headline,
        "priority": priority,
        "conditions": conditions,
        "notAssessed": not_assessed_text,
        "disclaimer": DISCLAIMER,
        "generatedBy": "template",
    }
    if fake:
        narrative["headline"] = "[TEST MODEL - NOT REAL] " + narrative["headline"]
    return narrative
