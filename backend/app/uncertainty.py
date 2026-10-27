"""
Ported from src/mock/engine/uncertainty.ts - same shape, same derivation rules
(confidence = mean of 'ok' predictions, reliability from assessed-count, missing modalities
from the not-assessed conditions' required inputs). One addition over the TS version
(section 4 of the Phase 2 spec): when a condition used only one of several possible
models, an extra message notes "based on <modality> only".

Wording note: "Demo Mode" phrasing from the TS version was dropped here since this is a
real inference backend, not a simulation - see the Phase 2 report for why.
"""


def _required_modalities(condition: str, fusion_config: dict) -> list[str]:
    components = fusion_config.get(condition, {}).get("components", [])
    return [c["modality"] for c in components if c.get("weight", 0) > 0]


def build_uncertainty(predictions: list[dict], fusion: dict, fusion_config: dict, fake: bool = False) -> dict:
    ok_predictions = [p for p in predictions if p["status"] == "ok"]
    confidence = (
        sum(p["confidence"] for p in ok_predictions) / len(ok_predictions)
        if ok_predictions
        else 0.0
    )

    assessed_count = len(fusion["assessedConditions"])
    total_in_scope = len(fusion.get("conditionsInScope") or fusion["assessedConditions"] + fusion["notAssessedConditions"])
    reliability = "adequate" if assessed_count == total_in_scope else "limited" if assessed_count >= 3 else "low"
    uncertainty_level = "low" if confidence >= 0.75 else "moderate" if confidence >= 0.5 else "high"

    missing: list[str] = []
    for condition in fusion["notAssessedConditions"]:
        for modality in _required_modalities(condition, fusion_config):
            if modality not in missing:
                missing.append(modality)

    messages = [
        "Confidence reflects model agreement and is not medical certainty.",
        "Missing or invalid inputs were excluded from this fusion run.",
    ]
    for result in fusion["perCondition"]:
        if result["riskLevel"] == "not_assessed":
            continue
        if result["condition"] == "diabetes":
            # diabetes has its own "best_available" strategy (app/fusion.py) - a
            # single combined-model contribution is the BEST signal, not a partial
            # one, so it must not trigger the generic "based on X only" message below.
            strategy = result.get("strategyUsed")
            if strategy == "combined" and result.get("notUsedModelIds"):
                messages.append(
                    f"diabetes: not used: {', '.join(result['notUsedModelIds'])} (combined model available)."
                )
            elif strategy == "clinical_only":
                messages.append("based on clinical data only: low confidence")
            elif strategy == "lab_only":
                messages.append("diabetes: based on lab data only.")
            continue
        total_possible = len(fusion_config.get(result["condition"], {}).get("components", []))
        if total_possible > 1 and len(result["contributions"]) == 1:
            modality = result["contributions"][0]["modality"]
            messages.append(f"{result['condition']}: based on {modality} only.")

    model_status = "FAKE TEST ARTIFACT - numbers are meaningless" if fake else "Backend inference (not a diagnosis)"

    return {
        "confidence": confidence,
        "uncertaintyLevel": uncertainty_level,
        "reliability": reliability,
        "dataCompleteness": {
            "available": len(fusion["modalitiesUsed"]),
            "total": 5,
            "missing": missing,
        },
        "modelStatus": model_status,
        "messages": messages,
    }
