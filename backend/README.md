# MedFusion backend

A local FastAPI service that takes a patient's inputs (any subset), runs whichever
trained models apply, fuses per condition, and returns JSON in the same shape as
`Analysis` in `../src/types/index.ts`, plus a doctor-readable narrative. It works with
zero, some, or all model artifacts present.

## Setup (Windows PowerShell)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Optional - needed for the chest X-ray / blood smear / ECG models. The rest of the
# app (tabular diabetes/hypertension models, API, narrative) works without this.
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

copy .env.example .env
# edit .env if you want to set GROQ_API_KEY / NARRATIVE_LLM=1
```

Run the tests (works with zero real artifacts - it generates its own fake ones):

```powershell
pytest -q
```

## Where real artifacts go

Train on Kaggle with the scripts in `../training/` (see `../training/README.md`), then
copy the output folders in:

```
backend/artifacts/
  tb/           tb_best.pt, comparison.json, roc.png, comparison.png, confusion_best.png, samples/
  malaria/      malaria_best.pt, comparison.json, ...
  leukemia/     leukemia_best.pt, comparison.json, ...   (no model yet - fine, see below)
  ecg/          ecg_best.pt, comparison.json, ...        (no model yet - fine, see below)
  tabular/      diabetes_lab_best.joblib, diabetes_lab_comparison.json,
                diabetes_clinical_best.joblib, diabetes_clinical_comparison.json,
                hypertension_clinical_best.joblib, hypertension_clinical_comparison.json,
                diabetes_fusion.json (optional - overrides the default diabetes fusion weights)
    reference/  any other trained model that doesn't match the per-modality contract
                above (e.g. a combined-feature diabetes model, or one trained without
                a required column) - just its comparison.json/csv/png, never a
                .pt/.joblib. Served as static files for the Models page; never loaded
                into the registry, never used for inference.
```

`*.pt` / `*.joblib` files are gitignored (large binaries); `comparison.json/csv` and
`.png` plots are committable. `backend/data/` (the runtime patient/analysis store) is
also gitignored - it's state, not a fixture.

A missing, corrupt, or incompatible artifact never crashes the app: that one model
slot is reported `missing`/`error` with a reason in `/health`, its condition becomes
`not_assessed`, and every other model keeps working. With **zero** artifacts present,
the app still starts and every condition is `not_assessed`. Leukemia and ECG having no
trained model yet is exactly this case - not a bug.

### Quality gate

A model that loads successfully can still be refused: if its own `comparison.json`
reports `test_auc` below `MIN_TEST_AUC` (env var, default **0.65**), the registry marks
it `state: "error"`, `reason: "below quality gate (test_auc=... < 0.65)"` in `/health`,
and never runs it - the file exists, but a model with no demonstrated signal must never
touch a real patient's result. This is on top of (not instead of) the existing
structural checks (a stored decision threshold, and for images: `arch`, `img_size`,
`mean`, `std` in the checkpoint) - those are already enforced by the predictor failing
to construct.

## Running it

```powershell
# With real artifacts in ./artifacts (the default):
uvicorn app.main:app --port 8000

# Or point at fake test artifacts (generated on the fly, numbers are meaningless):
python scripts/make_fake_artifacts.py --out artifacts_fake
$env:ARTIFACTS_DIR = "artifacts_fake"
uvicorn app.main:app --port 8000
```

Open `http://localhost:8000/docs` for interactive API docs.

To sanity-check every loaded model outside the API (one prediction each, printing
probability/threshold/decision against the model's own stored threshold):

```powershell
python scripts/predict_one.py
```

## API summary

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | Per-model load state (`loaded`/`missing`/`error`), reason, `simulatedOrFake`, sklearn/torch versions, `llmEnabled`. |
| GET | `/models` | Real metrics from each model's `comparison.json`, plus `/static/artifacts/...` plot URLs. |
| POST | `/patients` | Create a patient. |
| GET | `/patients`, `/patients/{id}` | List / fetch patients. |
| POST | `/analyze` | Multipart: `patient_id` (required), `explain_with_llm` (bool), any subset of clinical fields (`age`, `sex`, `bmi`, `smoking_history`, `hypertension`, `heart_disease`), lab fields (`hba1c`, `blood_glucose`), and files (`chest_xray`, `smear_cell`, `smear_field`, `ecg`). Returns an `Analysis`. Needs at least one usable input (422 otherwise). Out-of-range values are 422 (named field, never clipped); a bad file or missing field just means that model doesn't run. |
| GET | `/analyses`, `/analyses/{id}` | List / fetch past analyses. |
| POST | `/analyses/{id}/review` | Save a doctor's review status/note. |
| GET | `/flags` | List risk flags. |
| POST | `/flags/{id}/update` | Acknowledge / dismiss a flag. |

## Non-negotiable safety rules (what the tests enforce)

1. **Missing or invalid input is never a negative result.** A condition with zero
   contributing models is always `not_assessed`, never `low` (see `app/fusion.py`,
   `tests/test_fusion.py::test_a_missing_input_is_never_low_it_is_not_assessed`).
2. **Never impute.** Out-of-range clinical/lab values are rejected with HTTP 422
   naming the field - the value is never clipped (`app/validation.py`).
3. **A real high result is never hidden by missing data.** `overallRisk` is the
   highest level among *assessed* conditions; `incomplete_data` only when nothing
   could be assessed at all (`tests/test_fusion.py::test_b_a_lone_high_result_is_never_hidden`).
4. **A missing model file never crashes anything.** Every artifact load is wrapped
   and reported, not raised; the app starts with zero artifacts present
   (`app/registry.py`, `tests/test_registry.py`, `tests/test_api.py::test_zero_artifacts_app_starts_and_everything_is_not_assessed`).
5. **The narrative never says diagnosed/confirmed/cleared**, never calls missing
   data "negative", and every low result carries "does not rule out"
   (`app/narrative.py`, `tests/test_narrative.py`).
6. **No patient identifiers leave the machine.** The optional Groq rephrase step
   (`app/narrative_llm.py`) sends only `{condition, level, score, threshold, input
   type}` and the not-assessed list - no id/name/MRN/dates/raw feature values - and
   any failure (timeout, bad output, missing key) silently falls back to the
   deterministic template.
7. **Fake test artifacts are unmistakable.** `scripts/make_fake_artifacts.py` marks
   every comparison.json `"fake": true`; the registry surfaces this as
   `simulatedOrFake: true` in `/health`, `ModelPrediction.simulated: true`, and the
   narrative headline is prefixed `"[TEST MODEL - NOT REAL] "`.
