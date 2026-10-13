import {
  Patient,
  ModalityInput,
  ModalityType,
  ModelPrediction,
  FusionResult,
  Analysis,
  ExplainabilityResult,
  ModelMetadata,
  RiskFlag,
  Narrative,
  Condition
} from '@/types';

export interface RunAnalysisOptions {
  onProgress?: (stage: string, detail?: string) => void;
}

export type SmokingHistory = 'never' | 'former' | 'current' | 'not current' | 'ever' | 'No Info';

export interface ClinicalValues {
  age?: number;
  sex?: 'Female' | 'Male' | 'Other';
  bmi?: number;
  smokingHistory?: SmokingHistory;
  hypertension?: boolean;
  heartDisease?: boolean;
}

export interface LabValues {
  hba1c?: number;
  bloodGlucose?: number;
}

export interface AnalysisFiles {
  chestXray?: File;
  smearCell?: File;
  smearField?: File;
  ecg?: File;
}

export interface RunAnalysisInput {
  patientId: string;
  clinical?: ClinicalValues;
  lab?: LabValues;
  files?: AnalysisFiles;
  explainWithLlm?: boolean;
  /** Bookkeeping only - never sent to the backend. Lets callers (e.g. the replay
   * fallback in Part G) know this request came from a loaded demo case. */
  demoCaseId?: string;
}

export interface HealthModelStatus {
  id: string;
  modality: ModalityType;
  condition: Condition;
  state: 'loaded' | 'missing' | 'error';
  reason?: string;
  simulatedOrFake: boolean;
}

export interface HealthStatus {
  status: string;
  models: HealthModelStatus[];
  versions: { sklearn?: string | null; torch?: string | null };
  llmEnabled: boolean;
}

/** A structured, field-aware error for form validation (HTTP 422 from the backend). */
export class FieldValidationError extends Error {
  field?: string;
  constructor(message: string, field?: string) {
    super(message);
    this.name = 'FieldValidationError';
    this.field = field;
  }
}

export interface InferenceService {
  listPatients(filters?: any): Promise<Patient[]>;
  getPatient(id: string): Promise<Patient>;
  createPatient(patient: { name: string; age: number; sex: 'male' | 'female' | 'other'; mrn?: string }): Promise<Patient>;
  createDemoPatient(scenarioId?: string): Promise<Patient>;

  validateAndPreprocess(patientId: string, inputs: ModalityInput[]): Promise<ModalityInput[]>;
  predictModality(type: ModalityType, input: ModalityInput): Promise<ModelPrediction[]>;
  fuse(predictions: ModelPrediction[], modalitiesAvailable: ModalityType[]): Promise<FusionResult>;

  runAnalysis(input: RunAnalysisInput, opts?: RunAnalysisOptions): Promise<Analysis>;
  getAnalysis(id: string): Promise<Analysis>;
  listAnalyses(filters?: any): Promise<Analysis[]>;
  regenerateNarrative(analysisId: string, llm: boolean): Promise<Narrative>;

  getExplainability(analysisId: string): Promise<ExplainabilityResult[]>;
  listModels(): Promise<ModelMetadata[]>;

  listFlags(): Promise<RiskFlag[]>;
  updateFlag(id: string, action: string, note?: string): Promise<RiskFlag>;

  saveDoctorReview(analysisId: string, review: { status: 'pending' | 'reviewed'; note?: string }): Promise<Analysis>;

  getHealth(): Promise<HealthStatus>;
}
