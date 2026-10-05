# MedFusion Architecture and Design Decisions

## 1. Project Scope & Architecture
- **Goal:** Provide a demonstration UI for a late-fusion multimodal AI diagnostic engine.
- **Scope:** 80% frontend completion, no actual model backend currently connected. All data is strictly mocked via a deterministic engine.
- **Tech Stack:** React 18, Vite, TypeScript, Tailwind CSS v4, Zustand, TanStack Query, Recharts, Mulberry32.

## 2. Deterministic Mock Engine
- **Decision:** A pseudo-random number generator (PRNG), `mulberry32`, seeded by patient ID and available modalities, ensures that predictions, uncertainty values, explainability visuals, and flags are identical upon subsequent runs with identical inputs.
- **Reasoning:** This is critical for reliable demonstrations, as live unpredictable randomness would break the illusion of an AI model reliably diagnosing a patient. 
- **Limitations:** All synthetic metrics, scores, and findings are clinically meaningless and generated for UI purposes only. This must be prominently disclosed.

## 3. UI and Theming
- **Decision:** Deep navy (`#0f172a`) and teal (`#0d9488`) base palette. Theming uses Tailwind's color classes.
- **Reasoning:** Mirrors the PPT "MedFusion" branding (Med in navy, Fusion in teal). Prioritizes a clean, clinical, professional look without gradients or "cyberpunk" tropes.
- **Dark Mode:** Skipped by default to ensure maximum reliability and clean chart styling. Light theme is standard for clinical dashboards.

## 4. Modality and Late Fusion
- **Mapping:** 
  - Blood smear -> Malaria, Leukemia
  - Chest X-ray -> Tuberculosis
  - ECG -> Hypertension
  - Clinical/Lab -> Diabetes, Hypertension
- **Fusion Weighting:** Missing modalities simply drop out of the weighting. The fusion score is a re-normalized weighted average of the available inputs. 
- **Note:** The exact ECG to Hypertension model relationship is a design choice per the PPT's cited npj Digital Medicine paper on an ECG-based biomarker.

## 5. Security and Data Flow
- **Decision:** Uploads in Demo Mode are not actually uploaded. Files read by dropzones are kept locally in the browser or bypassed using a synthetic placeholder. 
- **Reasoning:** Prevents accidental upload of any sensitive data during a demo.

## 6. Service Layer
- **Decision:** `InferenceService.ts` defines a strict interface. `mockInferenceService.ts` implements it completely. `realInferenceService.ts` is provided as a stub.
- **Integration:** The `services/inference/index.ts` factory checks `VITE_INFERENCE_MODE` to export the correct instance. Real integration will only require filling out the HTTP calls in `realInferenceService.ts` and pointing the `.env` to the real API.
