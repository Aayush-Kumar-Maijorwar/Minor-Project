# Demo-day script

## Pre-flight checklist (do this before anyone is watching)

1. **Start the backend** with real artifacts if you have them, fake ones otherwise:
   ```powershell
   cd backend
   .venv\Scripts\Activate.ps1
   # real artifacts (if copied into backend/artifacts/ already):
   uvicorn app.main:app --port 8000
   # OR fake artifacts for a dry run:
   python scripts\make_fake_artifacts.py --out artifacts_fake
   $env:ARTIFACTS_DIR = "artifacts_fake"
   uvicorn app.main:app --port 8000
   ```
2. **Check `/health`** in a browser or `curl http://localhost:8000/health` - confirm
   every model you expect shows `"state": "loaded"`, and note whether
   `simulatedOrFake` is true anywhere (if so, the TEST MODELS banner will show - don't
   be surprised by it on stage).
3. **Start the frontend**: `npm run dev`, confirm the header chip says "Backend
   connected - N of N models loaded" (green). If it's amber/red, fix that first.
4. **Record fresh replays** so the offline fallback works even if the venue's network
   is unreliable mid-demo:
   ```powershell
   node scripts\record_replays.mjs
   ```
5. **Decide on Groq (AI wording) ahead of time:**
   - OFF (recommended for a live demo - no external network dependency, no latency
     surprise): leave `backend\.env`'s `NARRATIVE_LLM=0` (or unset). The "Simplify
     wording (AI)" button will show disabled with a tooltip - that's expected, say so
     if asked.
   - ON: set `NARRATIVE_LLM=1` and a real `GROQ_API_KEY` in `backend\.env`, restart
     the backend, confirm `/health`'s `llmEnabled` is `true`. Test the button once
     before going live.
6. Open the app to `/analysis/new` and leave it there - don't start mid-navigation.

## Case order and talking points

### 1. Full work-up (concerning)
- Every input filled in; sample images are chosen to be concerning.
- Talking points: "This is the ceiling case - every modality present." Point out the
  REVIEW priority banner, the per-condition gauges (raw score vs. the model's own flag
  threshold), and the "How was this decided?" expandable showing model weights.

### 2. Healthy screening
- Every input filled in; sample images are negative.
- Talking point: contrast with case 1 - same five condition cards, same layout, just a
  routine result. Emphasise every "No indication" card still names the input it was
  based on and still says "does not rule out" - the system never claims certainty.

### 3. Partial: chest X-ray + lab only
- Talking point: this is the realistic case - a patient rarely has every modality on
  day one. Show that TB and diabetes get assessed from what's present, while
  malaria/leukemia/hypertension show the grey "Not assessed" state with what to add
  next - never a false "negative".

### 4. Lab report only
- Talking point: the minimal-input case. One lab result in, diabetes assessed, the
  other four conditions cleanly "Not assessed". Good moment to show the Lab Report
  card's interpretive ranges (HbA1c, BMI) and that blood glucose only ever shows the
  raw value with a footnote - never an invented status.

### 5. Borderline values
- Talking point: HbA1c 6.3 / glucose 140 - deliberately near the flag threshold. Shows
  the amber BORDERLINE state, distinct from both FLAGGED and "no indication". This is
  the case to use if someone asks "what happens near the line?".

### 6. ECG + clinical (hypertension fusion)
- Talking point: shows two models fused for one condition - the per-model gauges (one
  for clinical, one for ECG, each with its own weight) and the explicit note that the
  ECG model is "a cardiac-abnormality screen, supporting evidence only, not a
  hypertension-specific test." Good moment to explain why fusion exists at all.

## If the backend goes down mid-demo

Re-running any of the six demo cases will fall back to the recorded replay and show a
clear amber "REPLAY - recorded <date>; backend offline" badge - say so out loud rather
than letting the audience think it's live. Hand-typed input (not a demo case) will
show a real "backend offline" error instead, by design - replay only ever covers the
rehearsed demo cases, never silently substitutes for a real request.

## What to say about limitations (have this ready)

> "Every model here is trained on a public dataset, not a clinical trial, and none of
> them are clinically validated - the Models page says so, and so does every
> narrative disclaimer. The late-fusion design means a missing input is never shown
> as a negative result; it's its own grey 'Not assessed' state, because treating
> absent data as reassuring would be the most dangerous mistake this kind of system
> could make. The ECG and hypertension models in particular are proxies, not direct
> measurements - that's stated on the Models page's Limitations panel and in the
> narrative itself whenever they contribute to a result."

<!-- TODO: fill in real sensitivity/specificity numbers here once real artifacts are trained and copied in -->
<!-- TODO: fill in the actual dataset names/links you used, from public/demo/ATTRIBUTION.md -->
