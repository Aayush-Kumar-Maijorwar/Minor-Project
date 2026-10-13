"""
Pydantic v2 schemas mirroring src/types/index.ts's Analysis shape, camelCase on the
wire. Internal modules (fusion/flags/uncertainty/narrative) build plain dicts with
camelCase keys directly - that lets Model.model_validate(dict) populate by alias with
no extra glue, and keeps those modules framework-free and easy to unit test.
"""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

Condition = Literal["diabetes", "hypertension", "malaria", "leukemia", "tuberculosis"]
ModalityType = Literal["bloodSmearCell", "bloodSmearField", "chestXray", "ecg", "clinical", "lab"]
ModalityStatus = Literal["available", "missing", "not_required", "pending"]
RiskLevel = Literal["low", "moderate", "high", "not_assessed"]
OverallRisk = Literal["low", "moderate", "high", "incomplete_data", "review_required"]


class Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Validation(Camel):
    ok: bool
    issues: list[str] = []


class ModalityInput(Camel):
    type: ModalityType
    status: ModalityStatus
    source: Literal["synthetic", "upload"] = "upload"
    validation: Optional[Validation] = None


class ModelPrediction(Camel):
    model_id: str
    condition: Condition
    modality: ModalityType
    score: float
    label: str
    confidence: float
    uncertainty: float
    status: Literal["ok", "skipped_missing_input"]
    simulated: bool
    model_version: str


class FusionContribution(Camel):
    modality: ModalityType
    model_id: str
    weight: float
    score: float


class FusionConditionResult(Camel):
    condition: Condition
    fused_score: float
    contributions: list[FusionContribution]
    risk_level: RiskLevel


class FusionResult(Camel):
    analysis_id: str
    per_condition: list[FusionConditionResult]
    overall_risk: OverallRisk
    dominant_condition: Optional[Condition] = None
    modalities_used: list[ModalityType]
    modalities_excluded: list[ModalityType]
    assessed_conditions: list[Condition]
    not_assessed_conditions: list[Condition]
    fusion_version: str
    simulated: bool
    note: str


class ExplainabilityFeature(Camel):
    name: str
    contribution: float
    direction: Literal["up", "down"]


class ExplainabilityResult(Camel):
    model_id: str
    kind: Literal["feature_importance", "heatmap", "ecg_segments"]
    features: Optional[list[ExplainabilityFeature]] = None
    simulated: bool = False


class DataCompleteness(Camel):
    available: int
    total: int
    missing: list[ModalityType]


class UncertaintyResult(Camel):
    confidence: float
    uncertainty_level: Literal["low", "moderate", "high"]
    reliability: Literal["adequate", "limited", "low"]
    data_completeness: DataCompleteness
    model_status: str
    messages: list[str]


class RiskFlag(Camel):
    id: str
    patient_id: str
    analysis_id: str
    condition: Optional[Condition] = None
    severity: Literal["high", "moderate", "low", "incomplete_data", "review_required"]
    reason: str
    created_at: str
    status: Literal["open", "acknowledged", "dismissed"] = "open"
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_action: Optional[str] = None


class NarrativeCondition(Camel):
    condition: Condition
    level: str
    line: str


class Narrative(Camel):
    headline: str
    priority: Literal["review", "routine", "incomplete"]
    conditions: list[NarrativeCondition]
    not_assessed: str
    disclaimer: str
    generated_by: Literal["template", "llm"]
    llm_text: Optional[str] = None


class DoctorReview(Camel):
    status: Literal["pending", "reviewed"]
    note: Optional[str] = None
    reviewed_at: Optional[str] = None


class SubmittedValues(Camel):
    """What the patient/clinician actually typed in - numbers and enum strings only,
    never files or identifiers - so a history view can still render a lab report card
    for an old analysis even though input file previews are never persisted."""
    clinical: Optional[dict] = None
    lab: Optional[dict] = None


class Analysis(Camel):
    id: str
    patient_id: str
    created_at: str
    inputs: list[ModalityInput]
    predictions: list[ModelPrediction]
    fusion: FusionResult
    explainability: list[ExplainabilityResult]
    uncertainty: UncertaintyResult
    flags: list[RiskFlag]
    versions: dict
    narrative: Narrative
    submitted_values: SubmittedValues
    doctor_review: Optional[DoctorReview] = None


class NarrativeRequest(Camel):
    llm: bool = False


class Patient(Camel):
    id: str
    mrn: str
    name: str
    age: int
    sex: Literal["male", "female", "other"]
    scenario_id: Optional[str] = None
    status: Literal["active", "inactive"] = "active"
    last_analysis_at: Optional[str] = None
    current_risk: Optional[OverallRisk] = None
    available_modalities: list[ModalityType] = []


class PatientCreate(Camel):
    mrn: str
    name: str
    age: int
    sex: Literal["male", "female", "other"]
    notes: Optional[str] = None


class ModelMetadata(Camel):
    id: str
    name: str
    condition: str
    input_modality: str
    status: str
    version: str
    last_updated: str
    explainability_support: bool
    integration_status: str
    metrics: Optional[list[dict]] = None
    plots: Optional[list[str]] = None
    comparison_url: Optional[str] = None
    fusion_url: Optional[str] = None
    fake: bool = False


class HealthModel(Camel):
    id: str
    modality: str
    condition: str
    state: Literal["loaded", "missing", "error"]
    reason: Optional[str] = None
    simulated_or_fake: bool = False


class HealthResponse(Camel):
    status: str
    models: list[HealthModel]
    versions: dict
    llm_enabled: bool


class ReviewUpdate(Camel):
    status: Literal["pending", "reviewed"]
    note: Optional[str] = None


class FlagUpdate(Camel):
    status: Literal["open", "acknowledged", "dismissed"]
    note: Optional[str] = None
