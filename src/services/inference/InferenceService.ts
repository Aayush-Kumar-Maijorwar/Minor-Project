import {
  Patient,
  ModalityInput,
  ModalityType,
  ModelPrediction,
  FusionResult,
  Analysis,
  ExplainabilityResult,
  ModelMetadata,
  RiskFlag
} from '@/types';

export interface RunAnalysisOptions {
  onProgress?: (stage: string, detail?: string) => void;
}

export interface InferenceService {
  listPatients(filters?: any): Promise<Patient[]>;
  getPatient(id: string): Promise<Patient>;
  createDemoPatient(scenarioId?: string): Promise<Patient>;
  
  validateAndPreprocess(patientId: string, inputs: ModalityInput[]): Promise<ModalityInput[]>;
  predictModality(type: ModalityType, input: ModalityInput): Promise<ModelPrediction[]>;
  fuse(predictions: ModelPrediction[], modalitiesAvailable: ModalityType[]): Promise<FusionResult>;
  
  runAnalysis(patientId: string, inputs: ModalityInput[], opts?: RunAnalysisOptions): Promise<Analysis>;
  getAnalysis(id: string): Promise<Analysis>;
  listAnalyses(filters?: any): Promise<Analysis[]>;
  
  getExplainability(analysisId: string): Promise<ExplainabilityResult[]>;
  listModels(): Promise<ModelMetadata[]>;
  
  listFlags(): Promise<RiskFlag[]>;
  updateFlag(id: string, action: string, note?: string): Promise<RiskFlag>;
  
  saveDoctorReview(analysisId: string, review: { status: 'pending' | 'reviewed'; note?: string }): Promise<Analysis>;
}
