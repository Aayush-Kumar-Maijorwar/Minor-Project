# MedFusion Dashboard

A late-fusion multimodal AI diagnostic engine with a doctor dashboard.
Created for: Minor Project, Phase I, CSE (AI), 5th Semester, BIT Durg.

## Setup and Run

1. **Install dependencies:**
   ```bash
   npm install
   ```
2. **Run dev server:**
   ```bash
   npm run dev
   ```
3. **Build:**
   ```bash
   npm run build
   ```

## Architecture
The application is built using React, Vite, TypeScript, and Tailwind CSS.
State is managed by Zustand and TanStack Query.
A central `InferenceService` handles all AI operations.

## Mock vs. Real Mode
Currently, the system runs entirely in Demo Mode using deterministic synthetic data (seeded using `mulberry32` logic). No actual models are attached.

To connect real models:
1. Open `.env` (or create one) and set `VITE_INFERENCE_MODE=real`.
2. Update `src/services/inference/realInferenceService.ts` to implement the actual HTTP endpoints for your models.
3. Make sure your models return data matching the schemas in `src/types/index.ts`.

## Future Integration Points (Search for `// FUTURE-INTEGRATION`)
- Actual Python backend inference server.
- Connect the `RealInferenceService` to real endpoints.
- Real medical image uploads for Blood Smear, Chest X-ray.
- Real explainability heatmaps (currently mocked via UI).
- Real Patient/History Database (currently stored in memory during the browser session).
