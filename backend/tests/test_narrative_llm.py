import httpx
import pytest

from app.fusion import ModelRun, simulate_fusion
from app.narrative import build_narrative
from app.narrative_llm import rephrase_with_llm

CONFIG = {
    "tuberculosis": {"components": [{"modality": "chestXray", "weight": 1.0}], "fused_threshold": 0.5},
    "diabetes": {"components": [{"modality": "lab", "weight": 1.0}], "fused_threshold": 0.5},
    "hypertension": {"components": [{"modality": "clinical", "weight": 1.0}], "fused_threshold": 0.5},
    "malaria": {"components": [{"modality": "bloodSmearCell", "weight": 1.0}], "fused_threshold": 0.5},
    "leukemia": {"components": [{"modality": "bloodSmearField", "weight": 1.0}], "fused_threshold": 0.5},
}


class FakeResponse:
    def __init__(self, content=None, status_code=200, raise_exc=None):
        self._content = content
        self.status_code = status_code
        self._raise_exc = raise_exc

    def raise_for_status(self):
        if self._raise_exc:
            raise self._raise_exc

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


class FakeClient:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc

    def post(self, *args, **kwargs):
        if self._exc:
            raise self._exc
        return self._response


@pytest.fixture()
def fusion_and_narrative():
    runs = [ModelRun(model_id="tb-resnet18", condition="tuberculosis", modality="chestXray", score=0.71, threshold=0.42)]
    fusion = simulate_fusion(runs, CONFIG, ["chestXray"])
    template = build_narrative(fusion, {"tb-resnet18": {"sensitivity": 0.95, "specificity": 0.88, "threshold": 0.42}})
    return fusion, template


def test_llm_disabled_returns_template_unchanged(monkeypatch, fusion_and_narrative):
    monkeypatch.setenv("NARRATIVE_LLM", "0")
    monkeypatch.setenv("GROQ_API_KEY", "some-key")
    fusion, template = fusion_and_narrative
    result = rephrase_with_llm(template, fusion)
    assert result is template


def test_missing_key_falls_back_to_template(monkeypatch, fusion_and_narrative):
    monkeypatch.setenv("NARRATIVE_LLM", "1")
    monkeypatch.setenv("GROQ_API_KEY", "")
    fusion, template = fusion_and_narrative
    result = rephrase_with_llm(template, fusion)
    assert result["generatedBy"] == "template"


def test_invented_number_falls_back_to_template(monkeypatch, fusion_and_narrative):
    monkeypatch.setenv("NARRATIVE_LLM", "1")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    fusion, template = fusion_and_narrative
    fake = FakeClient(response=FakeResponse(content="Tuberculosis flagged at 0.999, please review."))
    result = rephrase_with_llm(template, fusion, client=fake)
    assert result["generatedBy"] == "template"


def test_forbidden_word_falls_back_to_template(monkeypatch, fusion_and_narrative):
    monkeypatch.setenv("NARRATIVE_LLM", "1")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    fusion, template = fusion_and_narrative
    fake = FakeClient(response=FakeResponse(content="Tuberculosis confirmed at 0.71."))
    result = rephrase_with_llm(template, fusion, client=fake)
    assert result["generatedBy"] == "template"


def test_timeout_falls_back_to_template(monkeypatch, fusion_and_narrative):
    monkeypatch.setenv("NARRATIVE_LLM", "1")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    fusion, template = fusion_and_narrative
    fake = FakeClient(exc=httpx.TimeoutException("timed out"))
    result = rephrase_with_llm(template, fusion, client=fake)
    assert result["generatedBy"] == "template"


def test_success_path_is_accepted(monkeypatch, fusion_and_narrative):
    monkeypatch.setenv("NARRATIVE_LLM", "1")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    fusion, template = fusion_and_narrative
    fake = FakeClient(response=FakeResponse(
        content="Tuberculosis is flagged, with a score of 0.71 against a flag threshold of 0.42."
    ))
    result = rephrase_with_llm(template, fusion, client=fake)
    assert result["generatedBy"] == "llm"
    assert result["llmText"]
