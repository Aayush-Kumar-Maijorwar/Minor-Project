# MedFusion Dashboard

A late-fusion multimodal AI diagnostic engine with a doctor dashboard.
Created for: Minor Project, CSE (AI), 5th Semester, BIT Durg.

- **Phase 1** - frontend + deterministic mock fusion engine (`src/mock/`).
- **Phase 2** - real Python backend (`backend/`) - see `backend/README.md`.
- **Phase 3** - frontend wired to the real backend, demo cases, the result screen -
  this document.

## Setup and Run (Windows PowerShell)

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # leave GROQ_API_KEY blank unless you have one

# Generate fake artifacts so everything works before real Kaggle artifacts are copied in:
python scripts\make_fake_artifacts.py --out artifacts_fake
$env:ARTIFACTS_DIR = "artifacts_fake"
uvicorn app.main:app --port 8000
```

See `backend/README.md` for where real artifacts go, the full API, and the
non-negotiable safety rules the backend enforces.

### Frontend

```powershell
npm install
copy .env.example .env   # VITE_INFERENCE_MODE=real is the default; VITE_API_URL=http://localhost:8000
npm run dev
```

Set `VITE_INFERENCE_MODE=mock` in `.env` to develop against the built-in synthetic
engine instead of a running backend (no network calls at all).

### Build / test

```bash
npm run build
npm test
```

## Demo data

```powershell
# Generates clearly-labelled PLACEHOLDER images/ECG CSVs into public/demo/ - safe to
# run any time, works against fake artifacts, already committed so this is optional:
backend\.venv\Scripts\python.exe scripts\make_placeholder_demo.py

# Once real Kaggle artifacts are copied into backend/artifacts/, pull a few labelled
# real samples from each model's samples/ folder into public/demo/ instead:
backend\.venv\Scripts\python.exe scripts\import_demo_samples.py --artifacts backend\artifacts

# With the backend running, record a fresh offline fallback for every demo case:
node scripts\record_replays.mjs
```

See `public/demo/demo_cases.json` for the six demo cases and `DEMO_SCRIPT.md` for the
presenter's walkthrough.

## Architecture

React + Vite + TypeScript + Tailwind CSS. State via Zustand and TanStack Query. A
single `InferenceService` interface (`src/services/inference/`) is implemented twice:

- `mockInferenceService.ts` - deterministic synthetic engine (`src/mock/`), no backend
  needed.
- `realInferenceService.ts` - talks to the FastAPI backend in `backend/`.

Which one is used is controlled by `VITE_INFERENCE_MODE` (`real` is the default).

## Safety rules the frontend follows

The frontend never computes or changes a verdict - every risk level, score, threshold
and piece of verdict text comes from the backend (`fusion`, `narrative`). The UI only
formats what the backend returns. "Not assessed" is always its own grey state with an
icon and the word "Not assessed" - never styled as a real (green/low) result. If the
backend reports fake/test artifacts, every analysis screen shows a persistent red
"TEST MODELS" banner. No patient images are stored server-side; the UI only keeps file
previews in memory for the current session.
