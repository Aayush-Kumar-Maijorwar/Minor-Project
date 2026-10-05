import { InferenceService, RunAnalysisOptions } from './InferenceService';
import { Patient, ModalityInput, ModalityType, ModelPrediction, FusionResult, Analysis, ExplainabilityResult, ModelMetadata, RiskFlag } from '@/types';

export class RealInferenceService implements InferenceService {
  async listPatients(filters?: any): Promise<Patient[]> {
    // TODO: Implement GET /patients
    throw new Error('Not implemented');
  }

  async getPatient(id: string): Promise<Patient> {
    // TODO: Implement GET /patients/{id}
    throw new Error('Not implemented');
  }

  async createDemoPatient(scenarioId?: string): Promise<Patient> {
    throw new Error('Demo patient creation not supported in real mode');
  }

  async validateAndPreprocess(patientId: string, inputs: ModalityInput[]): Promise<ModalityInput[]> {
    // TODO: Implement POST /analysis/preprocess
    throw new Error('Not implemented');
  }

  async predictModality(type: ModalityType, input: ModalityInput): Promise<ModelPrediction[]> {
    // TODO: Implement POST /modality/{type}/predict
    throw new Error('Not implemented');
  }

  async fuse(predictions: ModelPrediction[], modalitiesAvailable: ModalityType[]): Promise<FusionResult> {
    // TODO: Implement POST /fusion
    throw new Error('Not implemented');
  }

  async runAnalysis(patientId: string, inputs: ModalityInput[], opts?: RunAnalysisOptions): Promise<Analysis> {
    // TODO: Implement POST /analysis (orchestration)
    throw new Error('Not implemented');
  }

  async getAnalysis(id: string): Promise<Analysis> {
    // TODO: Implement GET /analysis/{id}
    throw new Error('Not implemented');
  }

  async listAnalyses(filters?: any): Promise<Analysis[]> {
    // TODO: Implement GET /analysis
    throw new Error('Not implemented');
  }

  async getExplainability(analysisId: string): Promise<ExplainabilityResult[]> {
    // TODO: Implement GET /explainability/{analysisId}
    throw new Error('Not implemented');
  }

  async listModels(): Promise<ModelMetadata[]> {
    // TODO: Implement GET /models
    throw new Error('Not implemented');
  }

  async listFlags(): Promise<RiskFlag[]> {
    // TODO: Implement GET /flags
    throw new Error('Not implemented');
  }

  async updateFlag(id: string, action: string, note?: string): Promise<RiskFlag> {
    // TODO: Implement POST /flags/{id}/update
    throw new Error('Not implemented');
  }

  async saveDoctorReview(analysisId: string, review: { status: 'pending' | 'reviewed'; note?: string }): Promise<Analysis> {
    // TODO: Implement POST /analysis/{id}/review
    throw new Error('Not implemented');
  }
}
