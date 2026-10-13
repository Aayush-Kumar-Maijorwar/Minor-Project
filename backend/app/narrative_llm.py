"""
Optional LLM rephrase (section 7). OFF unless NARRATIVE_LLM=1, GROQ_API_KEY is set, AND the
request asks for it. Sends ONLY per-condition {condition, level, score, threshold, input type}
and the not-assessed list - no patient id/name/MRN/dates, no raw feature values - so no patient
identifiers ever leave the machine.

Any failure at all (timeout, HTTP error, missing key, validation failure) silently falls back
to the deterministic template; the template result is what build_narrative() already returned.
"""
import re

import httpx

from .config import get_settings

FORBIDDEN_WORDS = ["diagnose", "diagnosed", "confirm", "confirmed", "clear", "cleared"]
MAX_CHARS = 900
TIMEOUT_SECONDS = 6.0

SYSTEM_PROMPT = (
    "You rephrase medical screening findings into plain English for a doctor. Produce 3-5 "
    "plain sentences. Do not add any conditions, numbers, causes, or advice beyond what is "
    "given. Never use the words diagnose, confirm, or clear. Keep the phrase 'does not rule "
    "out' attached to any low-risk result."
)


def _number_tokens(text: str) -> set[str]:
    return set(re.findall(r"\d+\.?\d*%?", text))


def _allowed_numbers(template_narrative: dict) -> set[str]:
    text = template_narrative["headline"] + " "
    text += " ".join(c["line"] for c in template_narrative["conditions"]) + " "
    text += template_narrative["notAssessed"]
    return _number_tokens(text)


def _validate(text: str, template_narrative: dict, flagged_conditions: list[str]) -> bool:
    if not text or len(text) > MAX_CHARS:
        return False
    lowered = text.lower()
    if any(w in lowered for w in FORBIDDEN_WORDS):
        return False
    if not _number_tokens(text).issubset(_allowed_numbers(template_narrative)):
        return False
    return all(c.lower() in lowered for c in flagged_conditions)


def _build_findings(fusion: dict) -> list[dict]:
    findings = []
    for result in fusion["perCondition"]:
        if result["riskLevel"] == "not_assessed":
            continue
        findings.append({
            "condition": result["condition"],
            "level": result["riskLevel"],
            "score": round(result["fusedScore"], 2),
            "threshold": round(result.get("fusedThreshold", 0.5), 2),
            "inputType": ", ".join(c["modality"] for c in result["contributions"]),
        })
    return findings


def rephrase_with_llm(template_narrative: dict, fusion: dict, *, client: httpx.Client | None = None) -> dict:
    settings = get_settings()
    if not settings.llm_enabled:
        return template_narrative

    findings = _build_findings(fusion)
    payload = {
        "model": settings.groq_model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": str({"findings": findings, "notAssessed": fusion["notAssessedConditions"]}),
            },
        ],
    }

    try:
        if client is not None:
            resp = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                json=payload,
                timeout=TIMEOUT_SECONDS,
            )
        else:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                json=payload,
                timeout=TIMEOUT_SECONDS,
            )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return template_narrative

    flagged = [f["condition"] for f in findings if f["level"] == "high"]
    if not _validate(text, template_narrative, flagged):
        return template_narrative

    rephrased = dict(template_narrative)
    rephrased["llmText"] = text
    rephrased["generatedBy"] = "llm"
    return rephrased
