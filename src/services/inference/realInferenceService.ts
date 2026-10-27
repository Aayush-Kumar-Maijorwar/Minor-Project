import { InferenceService, RunAnalysisOptions, RunAnalysisInput, HealthStatus, FieldValidationError } from './InferenceService';
import { Patient, ModalityInput, ModalityType, ModelPrediction, FusionResult, Analysis, ExplainabilityResult, ModelMetadata, RiskFlag, Narrative } from '@/types';

export const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) || 'http://localhost:8000';

const KNOWN_FIELDS = ['hba1c', 'blood_glucose', 'age', 'bmi', 'sex', 'smoking_history', 'hypertension', 'heart_disease'];

function detailToFieldError(detail: string): FieldValidationError {
  const field = KNOWN_FIELDS.find(f => detail.startsWith(f + ' '));
  return new FieldValidationError(detail, field);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${BASE_URL}${path}`, init);
  } catch (e) {
    throw new Error(`Backend offline or unreachable (${BASE_URL}). ${e instanceof Error ? e.message : ''}`);
  }

  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      if (typeof body?.detail === 'string') detail = body.detail;
    } catch {
      // response body wasn't JSON - keep the status text
    }
    if (resp.status === 422) throw detailToFieldError(detail);
    if (resp.status === 404) throw new Error(detail || 'Not found');
    throw new Error(detail);
  }

  if (resp.status === 204) return undefined as unknown as T;
  return resp.json() as Promise<T>;
}

function buildAnalyzeForm(input: RunAnalysisInput): FormData {
  const form = new FormData();
  form.append('patient_id', input.patientId);
  form.append('explain_with_llm', String(!!input.explainWithLlm));

  const c = input.clinical;
  if (c) {
    if (c.age !== undefined) form.append('age', String(c.age));
    if (c.sex !== undefined) form.append('sex', c.sex);
    if (c.bmi !== undefined) form.append('bmi', String(c.bmi));
    if (c.smokingHistory !== undefined) form.append('smoking_history', c.smokingHistory);
    if (c.hypertension !== undefined) form.append('hypertension', String(c.hypertension));
    if (c.heartDisease !== undefined) form.append('heart_disease', String(c.heartDisease));
  }
  const l = input.lab;
  if (l) {
    if (l.hba1c !== undefined) form.append('hba1c', String(l.hba1c));
    if (l.bloodGlucose !== undefined) form.append('blood_glucose', String(l.bloodGlucose));
  }
  const f = input.files;
  if (f) {
    if (f.chestXray) form.append('chest_xray', f.chestXray);
    if (f.smearCell) form.append('smear_cell', f.smearCell);
    if (f.smearField) form.append('smear_field', f.smearField);
    if (f.ecg) form.append('ecg', f.ecg);
  }
  return form;
}

export class RealInferenceService implements InferenceService {
  async listPatients(_filters?: any): Promise<Patient[]> {
    return request<Patient[]>('/patients');
  }

  async getPatient(id: string): Promise<Patient> {
    return request<Patient>(`/patients/${encodeURIComponent(id)}`);
  }

  async createPatient(patient: { name: string; age: number; sex: 'male' | 'female' | 'other'; mrn?: string }): Promise<Patient> {
    return request<Patient>('/patients', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: patient.name,
        age: patient.age,
        sex: patient.sex,
        mrn: patient.mrn || `MRN-${Math.floor(Math.random() * 900000) + 100000}`
      })
    });
  }

  async createDemoPatient(_scenarioId?: string): Promise<Patient> {
    throw new Error('Demo patient creation is not supported against a real backend - use createPatient().');
  }

  async validateAndPreprocess(_patientId: string, inputs: ModalityInput[]): Promise<ModalityInput[]> {
    // The real backend validates as part of POST /analyze; there is no separate step.
    return inputs;
  }

  async predictModality(_type: ModalityType, _input: ModalityInput): Promise<ModelPrediction[]> {
    throw new Error('Not applicable in real mode - predictions come back from POST /analyze.');
  }

  async fuse(_predictions: ModelPrediction[], _modalitiesAvailable: ModalityType[]): Promise<FusionResult> {
    throw new Error('Not applicable in real mode - fusion happens server-side in POST /analyze.');
  }

  async runAnalysis(input: RunAnalysisInput, opts?: RunAnalysisOptions): Promise<Analysis> {
    opts?.onProgress?.('submitting', 'Sending inputs to the backend');
    const result = await request<Analysis>('/analyze', { method: 'POST', body: buildAnalyzeForm(input) });
    opts?.onProgress?.('done', 'Complete');
    return result;
  }

  async getAnalysis(id: string): Promise<Analysis> {
    return request<Analysis>(`/analyses/${encodeURIComponent(id)}`);
  }

  async listAnalyses(_filters?: any): Promise<Analysis[]> {
    return request<Analysis[]>('/analyses');
  }

  async regenerateNarrative(analysisId: string, llm: boolean): Promise<Narrative> {
    return request<Narrative>(`/analyses/${encodeURIComponent(analysisId)}/narrative`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ llm })
    });
  }

  async getExplainability(analysisId: string): Promise<ExplainabilityResult[]> {
    const analysis = await this.getAnalysis(analysisId);
    return analysis.explainability;
  }

  async listModels(): Promise<ModelMetadata[]> {
    return request<ModelMetadata[]>('/models');
  }

  async listFlags(): Promise<RiskFlag[]> {
    return request<RiskFlag[]>('/flags');
  }

  async updateFlag(id: string, action: string, note?: string): Promise<RiskFlag> {
    return request<RiskFlag>(`/flags/${encodeURIComponent(id)}/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: action, note })
    });
  }

  async saveDoctorReview(analysisId: string, review: { status: 'pending' | 'reviewed'; note?: string }): Promise<Analysis> {
    return request<Analysis>(`/analyses/${encodeURIComponent(analysisId)}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(review)
    });
  }

  async getHealth(): Promise<HealthStatus> {
    return request<HealthStatus>('/health');
  }
}
