"""
Pure late-fusion logic. No FastAPI/torch/pydantic imports here on purpose, so this
module is trivially unit-testable (see tests/test_fusion.py) and can never crash on
a missing model file - it only ever sees ModelRun objects for models that actually ran.

Safety invariant (see project README "Non-negotiable safety rules"): a condition with
zero contributing models is ALWAYS 'not_assessed', never derived as 'low'.
"""
from __future__ import annotations

from dataclasses import dataclass

ALL_CONDITIONS = ["diabetes", "hypertension", "malaria", "leukemia", "tuberculosis"]
ALL_MODALITIES = ["bloodSmearCell", "bloodSmearField", "chestXray", "ecg", "clinical", "lab"]

# Overall risk escalates to 'review_required' when a condition is high AND at least one
# contributing model's raw probability is this extreme.
REVIEW_PROBABILITY_THRESHOLD = 0.90

_LEVEL_RANK = {"low": 1, "moderate": 2, "high": 3}


def clip_threshold(t: float) -> float:
    return min(max(t, 1e-6), 1 - 1e-6)


def norm_score(p: float, t: float) -> float:
    """Map a model's own flag threshold t to 0.5 on a shared 0..1 fused scale.

    Monotone in p; norm_score(0, t) == 0, norm_score(1, t) == 1, norm_score(t, t) == 0.5.
    """
    t = clip_threshold(t)
    if p < t:
        return 0.5 * p / t
    return 0.5 + 0.5 * (p - t) / (1 - t)


@dataclass
class ModelRun:
    """One model that actually ran (valid input, status 'ok') for this analysis."""

    model_id: str
    condition: str
    modality: str
    score: float  # raw probability
    threshold: float  # this model's own decision threshold
    confidence: float = 0.0
    model_version: str = "v1"


def _condition_result(condition: str, config: dict, runs: list[ModelRun]) -> dict:
    components = config.get("components", [])
    weight_by_modality = {c["modality"]: c["weight"] for c in components}

    ran = [r for r in runs if weight_by_modality.get(r.modality, 0) > 0]
    if not ran:
        return {
            "condition": condition,
            "fusedScore": 0.0,
            "contributions": [],
            "riskLevel": "not_assessed",
        }

    total_weight = sum(weight_by_modality[r.modality] for r in ran)
    contributions = []
    fused = 0.0
    for r in ran:
        w = weight_by_modality[r.modality] / total_weight
        ns = norm_score(r.score, r.threshold)
        fused += w * ns
        contributions.append({
            "modality": r.modality,
            "modelId": r.model_id,
            "weight": w,
            "score": r.score,
            "threshold": r.threshold,
        })

    # Decision threshold on the fused 0..1 scale: exactly one model ran -> compare its own
    # norm_score to 0.5 (equivalent to p >= its own threshold); two or more -> the condition's
    # configured fused_threshold.
    t = config.get("fused_threshold", 0.5) if len(ran) >= 2 else 0.5

    if fused >= t:
        risk_level = "high"
    elif fused >= 0.6 * t:
        risk_level = "moderate"
    else:
        risk_level = "low"

    return {
        "condition": condition,
        "fusedScore": fused,
        "contributions": contributions,
        "riskLevel": risk_level,
        "fusedThreshold": t,
    }


def _diabetes_condition_result(config: dict, runs: list[ModelRun]) -> dict:
    """The 'best_available' policy (config/fusion.json: diabetes.strategy): when the
    combined lab+clinical model ran, it is used ALONE for the verdict - diabetes_lab
    and diabetes_clinical are never fused alongside it (no double-counting on the same
    underlying data). Otherwise, falls back to the normal late fusion of whichever of
    lab/clinical ran, exactly like any other condition.
    """
    combined_run = next((r for r in runs if r.modality == "clinicalLab"), None)
    classic_runs = [r for r in runs if r.modality in ("lab", "clinical")]

    if combined_run is not None:
        ns = norm_score(combined_run.score, combined_run.threshold)
        t = 0.5  # exactly one model contributes to the verdict - its own threshold, mapped to 0.5
        if ns >= t:
            risk_level = "high"
        elif ns >= 0.6 * t:
            risk_level = "moderate"
        else:
            risk_level = "low"
        result = {
            "condition": "diabetes",
            "fusedScore": ns,
            "contributions": [{
                "modality": "clinicalLab", "modelId": combined_run.model_id,
                "weight": 1.0, "score": combined_run.score, "threshold": combined_run.threshold,
            }],
            "riskLevel": risk_level,
            "fusedThreshold": t,
            "strategyUsed": "combined",
        }
        not_used = [r.model_id for r in classic_runs]
        if not_used:
            result["notUsedModelIds"] = not_used
        return result

    # No combined run (model missing/refused, or its inputs were incomplete) - fall
    # back to the generic weighted fusion, restricted to lab/clinical components only.
    classic_config = {**config, "components": [c for c in config.get("components", []) if c["modality"] in ("lab", "clinical")]}
    result = _condition_result("diabetes", classic_config, classic_runs)
    if result["riskLevel"] != "not_assessed":
        modalities = {c["modality"] for c in result["contributions"]}
        if modalities == {"lab", "clinical"}:
            result["strategyUsed"] = "fusion"
        elif modalities == {"lab"}:
            result["strategyUsed"] = "lab_only"
        elif modalities == {"clinical"}:
            result["strategyUsed"] = "clinical_only"
    return result


def simulate_fusion(runs: list[ModelRun], fusion_config: dict, modalities_used: list[str]) -> dict:
    """The Phase 1 rule, ported: overallRisk is the highest level among ASSESSED conditions,
    'incomplete_data' only when nothing could be assessed, never degraded by missing data.
    """
    per_condition = []
    for condition in ALL_CONDITIONS:
        config = fusion_config.get(condition, {"components": []})
        condition_runs = [r for r in runs if r.condition == condition]
        if condition == "diabetes" and config.get("strategy") == "best_available":
            per_condition.append(_diabetes_condition_result(config, condition_runs))
        else:
            per_condition.append(_condition_result(condition, config, condition_runs))

    assessed = [c["condition"] for c in per_condition if c["riskLevel"] != "not_assessed"]
    not_assessed = [c for c in ALL_CONDITIONS if c not in assessed]

    review_required = False
    overall_rank = 0
    dominant_condition = None
    dominant_score = -1.0

    for c in per_condition:
        if c["riskLevel"] == "not_assessed":
            continue
        if c["fusedScore"] > dominant_score:
            dominant_score, dominant_condition = c["fusedScore"], c["condition"]
        overall_rank = max(overall_rank, _LEVEL_RANK[c["riskLevel"]])
        if c["riskLevel"] == "high" and any(
            ct["score"] >= REVIEW_PROBABILITY_THRESHOLD for ct in c["contributions"]
        ):
            review_required = True

    if not assessed:
        overall_risk = "incomplete_data"
    elif review_required:
        overall_risk = "review_required"
    else:
        overall_risk = {1: "low", 2: "moderate", 3: "high"}[overall_rank]

    excluded = [m for m in ALL_MODALITIES if m not in modalities_used]

    return {
        "perCondition": per_condition,
        "overallRisk": overall_risk,
        "dominantCondition": dominant_condition,
        "modalitiesUsed": modalities_used,
        "modalitiesExcluded": excluded,
        "assessedConditions": assessed,
        "notAssessedConditions": not_assessed,
        "fusionVersion": "v1.0-backend",
        "simulated": False,
        "note": (
            f"{len(assessed)} of {len(ALL_CONDITIONS)} conditions assessed; missing or invalid "
            "inputs excluded the rest from this fusion run."
        ),
    }
