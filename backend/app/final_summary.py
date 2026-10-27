"""
Deterministic, LLM-free "simple JSON" + one-sentence summary ("final changes" spec,
part B). Pure - takes the already-computed fusion dict plus a caller-supplied
per-condition not-assessed reason, and never recomputes a verdict; the frontend
renders this verbatim.

Safety rules (same as narrative.py): a low result's summary line always carries
"does not rule out"; a missing/not-assessed condition never gets a score.
"""

RESULT_BY_LEVEL = {"high": "flagged", "moderate": "borderline", "low": "no_indication"}

CONDITION_LABELS = {
    "tuberculosis": "TB", "malaria": "malaria", "diabetes": "diabetes",
    "hypertension": "hypertension", "leukemia": "leukemia",
}

STRATEGY_BASIS = {
    "combined": "combined lab + clinical model",
    "fusion": "lab + clinical fusion",
    "lab_only": "lab model only",
    "clinical_only": "clinical model only",
}

MODALITY_BASIS = {
    "chestXray": "chest X-ray model", "bloodSmearCell": "blood-smear cell model",
    "bloodSmearField": "blood-smear field model", "ecg": "ECG model",
    "clinical": "clinical model", "lab": "lab model", "clinicalLab": "combined lab + clinical model",
}


def _basis(result: dict) -> str | None:
    if result["condition"] == "diabetes" and result.get("strategyUsed"):
        return STRATEGY_BASIS.get(result["strategyUsed"], "diabetes model")
    if len(result["contributions"]) == 1:
        return MODALITY_BASIS.get(result["contributions"][0]["modality"], result["contributions"][0]["modality"])
    return "combined model"


def _score_and_threshold(result: dict) -> tuple[float, float]:
    """diabetes always reports its own fused score/threshold (the 'best_available'
    strategy's decision scale); any other condition reports the deciding model's own
    raw probability/threshold when exactly one model ran, else its fused values."""
    if result["condition"] == "diabetes" or len(result["contributions"]) != 1:
        return round(result["fusedScore"], 2), round(result.get("fusedThreshold", 0.5), 2)
    c = result["contributions"][0]
    return round(c["score"], 2), round(c["threshold"], 2)


def _join_and(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def build_final_summary(fusion: dict, not_assessed_reasons: dict[str, str]) -> dict:
    conditions_in_scope = fusion.get("conditionsInScope") or [c["condition"] for c in fusion["perCondition"]]
    by_condition = {c["condition"]: c for c in fusion["perCondition"]}

    flagged, borderline, no_indication, not_assessed = [], [], [], []
    out_conditions: dict[str, dict] = {}

    for condition in conditions_in_scope:
        result = by_condition[condition]
        level = result["riskLevel"]
        if level == "not_assessed":
            not_assessed.append(condition)
            out_conditions[condition] = {
                "result": "not_assessed",
                "reason": not_assessed_reasons.get(condition, "not assessed"),
            }
            continue

        mapped = RESULT_BY_LEVEL[level]
        {"flagged": flagged, "borderline": borderline, "no_indication": no_indication}[mapped].append(condition)
        score, threshold = _score_and_threshold(result)
        out_conditions[condition] = {
            "result": mapped, "score": score, "threshold": threshold, "basis": _basis(result),
        }

    if not flagged and not borderline and not no_indication:
        summary = "No condition could be assessed: no usable input was provided."
        return {"summary": summary, "conditions": out_conditions}

    parts = []
    for condition in flagged:
        s, t = _score_and_threshold(by_condition[condition])
        parts.append(f"{CONDITION_LABELS[condition]} flagged (score {s:.2f} vs flag {t:.2f})")
    for condition in borderline:
        s, t = _score_and_threshold(by_condition[condition])
        parts.append(f"{CONDITION_LABELS[condition]} borderline (score {s:.2f} vs flag {t:.2f})")
    for condition in no_indication:
        s, t = _score_and_threshold(by_condition[condition])
        parts.append(f"{CONDITION_LABELS[condition]} no indication ({s:.2f} vs {t:.2f})")

    sentence = "; ".join(parts)
    if not_assessed:
        names = _join_and([CONDITION_LABELS[c] for c in not_assessed])
        reasons = ", ".join(not_assessed_reasons.get(c, "not assessed") for c in not_assessed)
        sentence += f"; {names} not assessed ({reasons})"
    sentence += "."
    sentence += (
        " Screening support only; low results do not rule out disease."
        if no_indication else " Screening support only."
    )

    return {"summary": sentence, "conditions": out_conditions}
