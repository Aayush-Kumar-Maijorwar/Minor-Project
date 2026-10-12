export type ModalityType = 'bloodSmear' | 'chestXray' | 'ecg' | 'clinical' | 'lab';
export type ModalityStatus = 'available' | 'missing' | 'not_required' | 'pending';
export type Condition = 'diabetes' | 'hypertension' | 'malaria' | 'leukemia' | 'tuberculosis';

export interface Patient {
  id: string;
  mrn: string;
  name: string;
  age: number;
  sex: 'male' | 'female' | 'other';
  scenarioId: string;
  status: 'active' | 'inactive';
  lastAnalysisAt?: string;
  currentRisk?: 'low' | 'moderate' | 'high' | 'incomplete_data' | 'review_required';
  availableModalities: ModalityType[];
  notes?: string;
}

export interface ModalityInput {
  type: ModalityType;
  status: ModalityStatus;
  source: 'synthetic' | 'upload';
  fileRef?: string;
  capturedAt?: string;
  validation?: { ok: boolean; issues: string[] };
  preprocessing?: { steps: string[]; state: 'queued' | 'running' | 'done' | 'warning' | 'skipped' };
}

export interface ClinicalData {
  age: number;
  sex: string;
  bmi: number;
  systolicBP: number;
  diastolicBP: number;
  heartRate: number;
  smokingStatus: string;
  familyHistoryDiabetes: boolean;
  familyHistoryHypertension: boolean;
  symptoms: string[];
}

export interface LabResult {
  fastingGlucose: number;
  hba1c: number;
  randomGlucose?: number;
  cholesterol?: number;
  hemoglobin?: number;
  wbcCount?: number;
  plateletCount?: number;
}

export interface ModelPrediction {
  modelId: string;
  condition: Condition;
  modality: ModalityType;
  score: number;
  label: string;
  confidence: number;
  uncertainty: number;
  status: 'ok' | 'skipped_missing_input';
  simulated: boolean;
  modelVersion: string;
}

export interface FusionContribution {
  modality: ModalityType;
  modelId: string;
  weight: number;
  score: number;
}

export interface FusionConditionResult {
  condition: Condition;
  fusedScore: number;
  contributions: FusionContribution[];
  riskLevel: 'low' | 'moderate' | 'high' | 'not_assessed';
}

export interface FusionResult {
  analysisId: string;
  perCondition: FusionConditionResult[];
  overallRisk: 'low' | 'moderate' | 'high' | 'incomplete_data' | 'review_required';
  dominantCondition?: Condition;
  modalitiesUsed: ModalityType[];
  modalitiesExcluded: ModalityType[];
  assessedConditions: Condition[];
  notAssessedConditions: Condition[];
  fusionVersion: string;
  simulated: true;
  note: string;
}

export interface ExplainabilityFeature {
  name: string;
  contribution: number;
  direction: 'up' | 'down';
}

export interface ExplainabilityRegion {
  x: number;
  y: number;
  weight: number;
  label: string;
}

export interface ExplainabilitySegment {
  startMs: number;
  endMs: number;
  weight: number;
  label: string;
}

export interface ExplainabilityResult {
  modelId: string;
  kind: 'feature_importance' | 'heatmap' | 'ecg_segments';
  features?: ExplainabilityFeature[];
  heatmap?: { grid: number[][]; regions: ExplainabilityRegion[] };
  segments?: ExplainabilitySegment[];
  simulated: true;
}

export interface UncertaintyResult {
  confidence: number;
  uncertaintyLevel: 'low' | 'moderate' | 'high';
  reliability: 'adequate' | 'limited' | 'low';
  dataCompleteness: { available: number; total: number; missing: ModalityType[] };
  modelStatus: string;
  messages: string[];
}

export interface RiskFlag {
  id: string;
  patientId: string;
  analysisId: string;
  condition?: Condition;
  severity: 'high' | 'moderate' | 'low' | 'incomplete_data' | 'review_required';
  reason: string;
  createdAt: string;
  status: 'open' | 'acknowledged' | 'dismissed';
  reviewedBy?: string;
  reviewedAt?: string;
  reviewAction?: string;
}

export interface Analysis {
  id: string;
  patientId: string;
  createdAt: string;
  inputs: ModalityInput[];
  predictions: ModelPrediction[];
  fusion: FusionResult;
  explainability: ExplainabilityResult[];
  uncertainty: UncertaintyResult;
  flags: RiskFlag[];
  versions: { models: Record<string, string>; fusion: string };
  doctorReview?: { status: 'pending' | 'reviewed'; note?: string; reviewedAt?: string };
}

export interface PredictionHistory {
  analysisId: string;
  patientId: string;
  createdAt: string;
  conditionsSummary: { condition: Condition; riskLevel: string }[];
  overallRisk: string;
  fusionVersion: string;
  modalitiesAvailable: ModalityType[];
}

export interface ModelMetadata {
  id: string;
  name: string;
  condition: Condition | 'all';
  inputModality: ModalityType | 'all';
  status: 'trained_baseline' | 'tuning' | 'planned' | 'demo_simulated';
  version: string;
  lastUpdated: string;
  explainabilitySupport: boolean;
  integrationStatus: 'mock' | 'ready_for_integration' | 'integrated';
  metrics?: { label: string; value: string; isPlaceholder: true }[];
}
