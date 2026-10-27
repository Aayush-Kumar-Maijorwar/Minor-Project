"""
FastAPI app. Multipart /analyze accepts ANY subset of inputs, runs whichever trained
models apply, fuses per condition, and returns an Analysis in the same shape as
src/types/index.ts - see README "Non-negotiable safety rules" for the invariants this
enforces (missing input is never a negative result, a real high is never hidden, a
missing model file never crashes anything, etc).
"""
import io
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image
from starlette.concurrency import run_in_threadpool

from . import final_summary as final_summary_mod
from . import flags as flags_mod
from . import fusion as fusion_mod
from . import narrative as narrative_mod
from . import narrative_llm
from . import schemas
from . import validation
from . import uncertainty as uncertainty_mod
from .config import get_settings
from .predictors.ecg import parse_heartbeat
from .registry import Registry
from .store import Store

ALL_MODALITIES = fusion_mod.ALL_MODALITIES

settings = get_settings()
registry = Registry(settings.artifacts_dir, Path(__file__).resolve().parent.parent / "config", settings.min_test_auc)
store = Store(settings.data_dir / "store.json")

app = FastAPI(title="MedFusion backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if settings.artifacts_dir.exists():
    app.mount("/static/artifacts", StaticFiles(directory=str(settings.artifacts_dir)), name="artifacts")

CLINICAL_MODEL_FIELDS = {
    "diabetes_clinical": ["age", "sex", "bmi", "smoking_history", "hypertension", "heart_disease"],
    "hypertension_clinical": ["age", "sex", "bmi", "smoking_history", "heart_disease"],
}
LAB_MODEL_FIELDS = {"diabetes_lab": ["hba1c", "blood_glucose"]}
# "best_available" strategy (app/fusion.py): when every one of these is present, the
# combined model runs ALONGSIDE diabetes_lab/diabetes_clinical (so modality
# availability for lab/clinical stays accurate) but fusion.py uses it ALONE for the
# diabetes verdict - never double-counted with the two single-modality models.
DIABETES_COMBINED_FIELDS = ["age", "sex", "bmi", "smoking_history", "hypertension", "heart_disease", "hba1c", "blood_glucose"]
MODEL_CONDITION = {"diabetes_clinical": "diabetes", "hypertension_clinical": "hypertension", "diabetes_lab": "diabetes"}
FIELD_TO_COLUMN = {"sex": "gender", "hba1c": "HbA1c_level", "blood_glucose": "blood_glucose_level"}
FILE_SLOTS = {
    "chestXray": ("tb", "tuberculosis"),
    "bloodSmearCell": ("malaria", "malaria"),
    "bloodSmearField": ("leukemia", "leukemia"),
}
# Every file-driven modality's underlying registry slot, incl. ecg (not itself a
# FILE_SLOTS entry since its condition, hypertension, can also be assessed without it).
MODALITY_SLOT_ID = {"chestXray": "tb", "bloodSmearCell": "malaria", "bloodSmearField": "leukemia", "ecg": "ecg"}

LAB_FIELD_LABELS = {"hba1c": "HbA1c", "blood_glucose": "blood glucose"}
CLINICAL_FIELD_LABELS = {
    "age": "age", "sex": "sex", "bmi": "BMI", "smoking_history": "smoking history",
    "hypertension": "known hypertension", "heart_disease": "known heart disease",
}
DIABETES_CLINICAL_REQUIRED = set(CLINICAL_MODEL_FIELDS["diabetes_clinical"])
HYPERTENSION_CLINICAL_REQUIRED = set(CLINICAL_MODEL_FIELDS["hypertension_clinical"])


def _model_loaded_for_modality(modality: str) -> bool:
    slot = registry.slots.get(MODALITY_SLOT_ID.get(modality, ""))
    return bool(slot and slot.state == "loaded")


def _not_assessed_reason(condition: str, clinical_fields: dict, lab_fields: dict, files: dict) -> str:
    """Caller-supplied reason text for final_summary.build_final_summary - kept here
    (not in final_summary.py) because it needs the raw request fields, not just the
    already-computed fusion result."""
    if condition == "tuberculosis":
        return "no chest X-ray provided" if not files.get("chestXray") else "chest X-ray could not be used"
    if condition == "malaria":
        return "no blood-smear cell image provided" if not files.get("bloodSmearCell") else "blood-smear cell image could not be used"
    if condition == "diabetes":
        lab_present = set(lab_fields)
        if lab_present and lab_present != {"hba1c", "blood_glucose"}:
            missing = {"hba1c", "blood_glucose"} - lab_present
            given_label = LAB_FIELD_LABELS[next(iter(lab_present))]
            missing_label = LAB_FIELD_LABELS[next(iter(missing))]
            return f"{given_label} given but {missing_label} missing"
        clinical_present = set(clinical_fields)
        if clinical_present and not DIABETES_CLINICAL_REQUIRED.issubset(clinical_present):
            missing = DIABETES_CLINICAL_REQUIRED - clinical_present
            return "clinical data given but missing: " + ", ".join(CLINICAL_FIELD_LABELS[f] for f in sorted(missing))
        return "no lab or clinical data provided"
    if condition == "hypertension":
        clinical_present = set(clinical_fields)
        if clinical_present and not HYPERTENSION_CLINICAL_REQUIRED.issubset(clinical_present):
            missing = HYPERTENSION_CLINICAL_REQUIRED - clinical_present
            return "clinical data given but missing: " + ", ".join(CLINICAL_FIELD_LABELS[f] for f in sorted(missing))
        return "no clinical data provided"
    return "not assessed"


def _gen_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row(fields: dict) -> dict:
    return {FIELD_TO_COLUMN.get(k, k): v for k, v in fields.items()}


def _to_prediction(pred: dict) -> dict:
    score = pred["score"]
    label = "High Risk" if score > 0.65 else "Moderate Risk" if score > 0.35 else "Normal"
    return {
        "modelId": pred["modelId"], "condition": pred["condition"], "modality": pred["modality"],
        "score": score, "label": label, "confidence": pred["confidence"],
        "uncertainty": 1 - pred["confidence"], "status": "ok", "simulated": pred.get("simulated", False),
        "modelVersion": "v1.0.0",
        "_threshold": pred["threshold"], "_drivers": pred.get("drivers"),
    }


def _skipped(model_id: str, modality: str, condition: str) -> dict:
    return {
        "modelId": model_id, "condition": condition, "modality": modality, "score": 0.0,
        "label": "Not Assessed", "confidence": 0.0, "uncertainty": 1.0,
        "status": "skipped_missing_input", "simulated": False, "modelVersion": "v1.0.0",
        "_threshold": 0.5, "_drivers": None,
    }


def _clean_prediction(p: dict) -> dict:
    return {k: v for k, v in p.items() if not k.startswith("_")}


def _modality_input(modality_type: str, ran: bool, issues: list[str]) -> dict:
    return {
        "type": modality_type,
        "status": "available" if ran else "missing",
        "source": "upload",
        "validation": {"ok": len(issues) == 0, "issues": issues},
    }


def _validate_image_bytes(raw: bytes) -> str | None:
    """Returns an issue string, or None if the image is usable."""
    if len(raw) > validation.MAX_UPLOAD_BYTES:
        return "file exceeds 15 MB"
    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
        img2 = Image.open(io.BytesIO(raw))  # verify() invalidates the handle; reopen to read size
        w, h = img2.size
    except Exception:
        return "file could not be decoded as an image"
    if w < validation.MIN_IMAGE_SIDE or h < validation.MIN_IMAGE_SIDE:
        return "image must be at least 32px per side"
    return None


def _run_tabular_group(fields: dict, model_fields: dict, predictions: list[dict], issues: list[str]):
    for model_id, required in model_fields.items():
        condition = MODEL_CONDITION[model_id]
        missing = [f for f in required if f not in fields]
        if missing:
            issues.append(f"{model_id}: missing {', '.join(missing)}")
            predictions.append(_skipped(model_id, "clinical" if model_id != "diabetes_lab" else "lab", condition))
            continue
        pred = registry.run_tabular(model_id, _row({f: fields[f] for f in required}))
        if pred is None:
            issues.append(f"{model_id}: model not available")
            predictions.append(_skipped(model_id, "clinical" if model_id != "diabetes_lab" else "lab", condition))
        else:
            predictions.append(_to_prediction(pred))


def _run_analysis(
    patient: dict, clinical_fields: dict, lab_fields: dict, files: dict, explain_with_llm: bool
) -> dict:
    analysis_id = _gen_id("AN")
    predictions: list[dict] = []
    issues_by_modality: dict[str, list[str]] = {m: [] for m in ALL_MODALITIES}
    provided: dict[str, bool] = {m: False for m in ALL_MODALITIES}
    ignored_inputs: list[dict] = []

    if clinical_fields:
        provided["clinical"] = True
        _run_tabular_group(clinical_fields, CLINICAL_MODEL_FIELDS, predictions, issues_by_modality["clinical"])
    if lab_fields:
        provided["lab"] = True
        _run_tabular_group(lab_fields, LAB_MODEL_FIELDS, predictions, issues_by_modality["lab"])

    combined_fields = {**clinical_fields, **lab_fields}
    if all(f in combined_fields for f in DIABETES_COMBINED_FIELDS):
        pred = registry.run_tabular("diabetes_combined", _row({f: combined_fields[f] for f in DIABETES_COMBINED_FIELDS}))
        if pred is not None:
            predictions.append(_to_prediction(pred))
        # else: combined model missing/refused - fusion.py's best_available strategy
        # falls back to diabetes_lab/diabetes_clinical automatically, no issue needed
        # (clinicalLab isn't a user-facing input modality of its own).

    for modality, (slot_id, condition) in FILE_SLOTS.items():
        upload = files.get(modality)
        if upload is None:
            continue
        if not _model_loaded_for_modality(modality):
            slot = registry.slots.get(slot_id)
            reason = (slot.reason if slot else None) or "model not available"
            ignored_inputs.append({"modality": modality, "filename": upload.filename, "reason": reason})
            continue
        provided[modality] = True
        raw = upload.file.read()
        issue = _validate_image_bytes(raw)
        if issue:
            issues_by_modality[modality].append(issue)
            predictions.append(_skipped(slot_id, modality, condition))
            continue
        pred = registry.run_image(slot_id, raw)
        if pred is None:
            issues_by_modality[modality].append(f"{slot_id}: model not available")
            predictions.append(_skipped(slot_id, modality, condition))
        else:
            predictions.append(_to_prediction(pred))

    ecg_upload = files.get("ecg")
    if ecg_upload is not None:
        if not _model_loaded_for_modality("ecg"):
            ecg_slot = registry.slots.get("ecg")
            reason = (ecg_slot.reason if ecg_slot else None) or "model not available"
            ignored_inputs.append({"modality": "ecg", "filename": ecg_upload.filename, "reason": reason})
        else:
            provided["ecg"] = True
            raw = ecg_upload.file.read()
            if len(raw) > validation.MAX_UPLOAD_BYTES:
                issues_by_modality["ecg"].append("file exceeds 15 MB")
                predictions.append(_skipped("ecg", "ecg", "hypertension"))
            else:
                try:
                    values = parse_heartbeat(raw)
                except ValueError as e:
                    issues_by_modality["ecg"].append(str(e))
                    predictions.append(_skipped("ecg", "ecg", "hypertension"))
                else:
                    pred = registry.run_ecg(values)
                    if pred is None:
                        issues_by_modality["ecg"].append("ecg: model not available")
                        predictions.append(_skipped("ecg", "ecg", "hypertension"))
                    else:
                        predictions.append(_to_prediction(pred))

    # A modality is 'available' only if >=1 of its models actually ran (status 'ok') -
    # partial/invalid input that ran nothing is reported as 'missing' with the reason why.
    ran_modalities = {p["modality"] for p in predictions if p["status"] == "ok"}
    modalities_used = [m for m in ALL_MODALITIES if m in ran_modalities]
    inputs = [_modality_input(m, m in ran_modalities, issues_by_modality[m]) for m in ALL_MODALITIES if provided[m]]
    inputs += [_modality_input(m, False, []) for m in ALL_MODALITIES if not provided[m]]

    runs = [
        fusion_mod.ModelRun(
            model_id=p["modelId"], condition=p["condition"], modality=p["modality"],
            score=p["score"], threshold=p["_threshold"], confidence=p["confidence"],
        )
        for p in predictions if p["status"] == "ok"
    ]
    conditions_in_scope = registry.conditions_in_scope()
    fusion = fusion_mod.simulate_fusion(runs, registry.fusion_config, modalities_used, conditions_in_scope)
    fusion["analysisId"] = analysis_id

    flags_list = flags_mod.build_flags(analysis_id, patient["id"], fusion)
    fake = any(p.get("simulated") for p in predictions)
    uncertainty = uncertainty_mod.build_uncertainty(predictions, fusion, registry.fusion_config, fake=fake)

    explainability = []
    drivers_by_model = {}
    for p in predictions:
        if p["status"] == "ok" and p.get("_drivers"):
            drivers_by_model[p["modelId"]] = p["_drivers"]
            explainability.append({
                "modelId": p["modelId"],
                "kind": "feature_importance",
                "features": [
                    {"name": d["name"], "contribution": d["contribution"], "direction": d["direction"]}
                    for d in p["_drivers"]
                ],
                "simulated": p.get("simulated", False),
            })

    model_meta = registry.narrative_model_meta()
    narrative = narrative_mod.build_narrative(fusion, model_meta, drivers_by_model, fake=fake)
    if explain_with_llm:
        narrative = narrative_llm.rephrase_with_llm(narrative, fusion)

    not_assessed_reasons = {
        c: _not_assessed_reason(c, clinical_fields, lab_fields, files)
        for c in fusion["notAssessedConditions"]
    }
    final_summary = final_summary_mod.build_final_summary(fusion, not_assessed_reasons)

    analysis = {
        "id": analysis_id,
        "patientId": patient["id"],
        "createdAt": _now(),
        "inputs": inputs,
        "predictions": [_clean_prediction(p) for p in predictions],
        "fusion": fusion,
        "explainability": explainability,
        "uncertainty": uncertainty,
        "flags": flags_list,
        "versions": {"models": {p["modelId"]: "v1" for p in predictions}, "fusion": fusion["fusionVersion"]},
        "narrative": narrative,
        "submittedValues": {"clinical": clinical_fields or None, "lab": lab_fields or None},
        "conditionsInScope": conditions_in_scope,
        "ignoredInputs": ignored_inputs,
        "finalSummary": final_summary,
    }
    store.add_analysis(analysis)
    store.update_patient(patient["id"], lastAnalysisAt=analysis["createdAt"], currentRisk=fusion["overallRisk"])
    return analysis


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health", response_model=schemas.HealthResponse)
def health():
    return schemas.HealthResponse(
        status="ok",
        models=[schemas.HealthModel.model_validate(m) for m in registry.health_models()],
        versions=registry.versions(),
        llm_enabled=settings.llm_enabled,
        conditions_in_scope=registry.conditions_in_scope(),
    )


@app.get("/models", response_model=list[schemas.ModelMetadata])
def list_models():
    return [schemas.ModelMetadata.model_validate(m) for m in registry.models_metadata()]


@app.post("/patients", response_model=schemas.Patient)
def create_patient(body: schemas.PatientCreate):
    patient = {
        "id": _gen_id("PT"), "mrn": body.mrn, "name": body.name, "age": body.age,
        "sex": body.sex, "status": "active", "availableModalities": [],
    }
    store.add_patient(patient)
    return schemas.Patient.model_validate(patient)


@app.get("/patients", response_model=list[schemas.Patient])
def list_patients():
    return [schemas.Patient.model_validate(p) for p in store.list_patients()]


@app.get("/patients/{patient_id}", response_model=schemas.Patient)
def get_patient(patient_id: str):
    p = store.get_patient(patient_id)
    if not p:
        raise HTTPException(status_code=404, detail="patient not found")
    return schemas.Patient.model_validate(p)


@app.post("/analyze", response_model=schemas.Analysis)
async def analyze(
    patient_id: str = Form(...),
    explain_with_llm: bool = Form(False),
    age: float | None = Form(None),
    sex: str | None = Form(None),
    bmi: float | None = Form(None),
    smoking_history: str | None = Form(None),
    hypertension: bool | None = Form(None),
    heart_disease: bool | None = Form(None),
    hba1c: float | None = Form(None),
    blood_glucose: float | None = Form(None),
    chest_xray: UploadFile | None = File(None),
    smear_cell: UploadFile | None = File(None),
    smear_field: UploadFile | None = File(None),
    ecg: UploadFile | None = File(None),
):
    patient = store.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="patient not found")

    clinical_fields = {k: v for k, v in {
        "age": age, "sex": sex, "bmi": bmi, "smoking_history": smoking_history,
        "hypertension": hypertension, "heart_disease": heart_disease,
    }.items() if v is not None}
    lab_fields = {k: v for k, v in {"hba1c": hba1c, "blood_glucose": blood_glucose}.items() if v is not None}

    validation.validate_clinical_fields(age=age, sex=sex, bmi=bmi, smoking_history=smoking_history)
    validation.validate_lab_fields(hba1c=hba1c, blood_glucose=blood_glucose)

    files = {"chestXray": chest_xray, "bloodSmearCell": smear_cell, "bloodSmearField": smear_field, "ecg": ecg}
    usable_file_provided = any(
        f is not None and _model_loaded_for_modality(modality) for modality, f in files.items()
    )
    if not clinical_fields and not lab_fields and not usable_file_provided:
        raise HTTPException(status_code=422, detail="Provide at least one input")

    result = await run_in_threadpool(_run_analysis, patient, clinical_fields, lab_fields, files, explain_with_llm)
    return schemas.Analysis.model_validate(result)


@app.get("/analyses", response_model=list[schemas.Analysis])
def list_analyses():
    return [schemas.Analysis.model_validate(a) for a in store.list_analyses()]


@app.get("/analyses/{analysis_id}", response_model=schemas.Analysis)
def get_analysis(analysis_id: str):
    a = store.get_analysis(analysis_id)
    if not a:
        raise HTTPException(status_code=404, detail="analysis not found")
    return schemas.Analysis.model_validate(a)


@app.post("/analyses/{analysis_id}/narrative", response_model=schemas.Narrative)
def regenerate_narrative(analysis_id: str, body: schemas.NarrativeRequest):
    """Re-render the narrative for an already-computed analysis - never reruns models.
    Template by default; the AI rephrase only runs if the caller asks AND it's enabled
    server-side, and silently falls back to the template on any failure (same rule as
    POST /analyze). Not persisted - the stored analysis keeps its original narrative."""
    a = store.get_analysis(analysis_id)
    if not a:
        raise HTTPException(status_code=404, detail="analysis not found")

    template = {k: v for k, v in a["narrative"].items() if k != "llmText"}
    template["generatedBy"] = "template"
    narrative = narrative_llm.rephrase_with_llm(template, a["fusion"]) if body.llm else template
    return schemas.Narrative.model_validate(narrative)


@app.post("/analyses/{analysis_id}/review", response_model=schemas.Analysis)
def review_analysis(analysis_id: str, body: schemas.ReviewUpdate):
    if not store.get_analysis(analysis_id):
        raise HTTPException(status_code=404, detail="analysis not found")
    updated = store.update_analysis(
        analysis_id,
        doctorReview={"status": body.status, "note": body.note, "reviewedAt": _now()},
    )
    return schemas.Analysis.model_validate(updated)


@app.get("/flags", response_model=list[schemas.RiskFlag])
def list_flags():
    return [schemas.RiskFlag.model_validate(f) for f in store.list_flags()]


@app.post("/flags/{flag_id}/update", response_model=schemas.RiskFlag)
def update_flag(flag_id: str, body: schemas.FlagUpdate):
    updated = store.update_flag(
        flag_id, status=body.status, reviewedAt=_now(), reviewAction=body.note or body.status
    )
    if not updated:
        raise HTTPException(status_code=404, detail="flag not found")
    return schemas.RiskFlag.model_validate(updated)
