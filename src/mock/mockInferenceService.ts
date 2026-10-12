import { InferenceService, RunAnalysisOptions } from '../services/inference/InferenceService';
import { 
  Patient, ModalityInput, ModalityType, ModelPrediction, FusionResult, 
  Analysis, ExplainabilityResult, ModelMetadata, RiskFlag, UncertaintyResult 
} from '@/types';
import { getMockPatient, mockPatients } from './data/mockPatients';
import { simulateModalityPredictions } from './engine/modalityModelSim';
import { simulateLateFusion } from './engine/lateFusionSim';
import { buildFlags } from './engine/flags';
import { buildUncertainty } from './engine/uncertainty';

// Helper to generate IDs
const generateId = () => Math.random().toString(36).substr(2, 9);

const MOCK_MODELS: ModelMetadata[] = [
  { id: 'model-clin-v1', name: 'Clinical Data Model', condition: 'all', inputModality: 'clinical', status: 'trained_baseline', version: 'v1.0.0', lastUpdated: '2026-09-15', explainabilitySupport: true, integrationStatus: 'mock' },
  { id: 'model-lab-v1', name: 'Laboratory Data Model', condition: 'diabetes', inputModality: 'lab', status: 'trained_baseline', version: 'v1.0.0', lastUpdated: '2026-09-15', explainabilitySupport: true, integrationStatus: 'mock' },
  { id: 'model-ecg-v1', name: 'ECG Biomarker Model', condition: 'hypertension', inputModality: 'ecg', status: 'tuning', version: 'v0.9.0-beta', lastUpdated: '2026-10-01', explainabilitySupport: true, integrationStatus: 'mock' },
  { id: 'model-smear-v1', name: 'Blood Smear Analysis', condition: 'all', inputModality: 'bloodSmear', status: 'planned', version: 'v0.1.0-alpha', lastUpdated: '2026-10-05', explainabilitySupport: true, integrationStatus: 'mock' },
  { id: 'model-cxr-v2', name: 'CXR Pathology Model', condition: 'tuberculosis', inputModality: 'chestXray', status: 'planned', version: 'v0.1.0-alpha', lastUpdated: '2026-10-05', explainabilitySupport: true, integrationStatus: 'mock' }
];

let globalAnalyses: Analysis[] = [];
let globalFlags: RiskFlag[] = [];

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export class MockInferenceService implements InferenceService {
  async listPatients(filters?: any): Promise<Patient[]> {
    return [...mockPatients];
  }

  async getPatient(id: string): Promise<Patient> {
    const p = getMockPatient(id);
    if (!p) throw new Error('Patient not found');
    return p;
  }

  async createDemoPatient(scenarioId?: string): Promise<Patient> {
    const id = `DEMO-${generateId()}`;
    const p: Patient = {
      id,
      mrn: `MRN-${Math.floor(Math.random() * 900000) + 100000}`,
      name: `Demo Patient ${id.slice(-4)}`,
      age: 45,
      sex: 'other',
      scenarioId: scenarioId || 'healthy',
      status: 'active',
      availableModalities: ['clinical', 'lab']
    };
    mockPatients.push(p);
    return p;
  }

  async validateAndPreprocess(patientId: string, inputs: ModalityInput[]): Promise<ModalityInput[]> {
    return inputs.map(input => ({
      ...input,
      validation: { ok: true, issues: [] },
      preprocessing: { steps: ['Validated', 'Normalized'], state: 'done' }
    }));
  }

  async predictModality(type: ModalityType, input: ModalityInput): Promise<ModelPrediction[]> {
    // This is handled in runAnalysis directly for orchestration, but we can return stub here
    return [];
  }

  async fuse(predictions: ModelPrediction[], modalitiesAvailable: ModalityType[]): Promise<FusionResult> {
    return simulateLateFusion(predictions, modalitiesAvailable);
  }

  async runAnalysis(patientId: string, inputs: ModalityInput[], opts?: RunAnalysisOptions): Promise<Analysis> {
    const patient = await this.getPatient(patientId);
    
    opts?.onProgress?.('preprocessing', 'Validating inputs');
    await sleep(400);
    const preprocessedInputs = await this.validateAndPreprocess(patientId, inputs);
    
    opts?.onProgress?.('predicting', 'Running modality models');
    await sleep(600);
    const predictions = simulateModalityPredictions(patientId, preprocessedInputs, patient.scenarioId);
    
    opts?.onProgress?.('fusing', 'Executing late fusion');
    await sleep(400);
    const activeModalities = preprocessedInputs.filter(i => i.status === 'available').map(i => i.type);
    const fusion = simulateLateFusion(predictions, activeModalities);
    
    opts?.onProgress?.('explainability', 'Generating explanations and uncertainty bounds');
    await sleep(500);

    const uncertainty: UncertaintyResult = buildUncertainty(predictions, fusion);

    const explainability: ExplainabilityResult[] = predictions.filter(p => p.status === 'ok').map(p => {
      let kind: 'feature_importance' | 'heatmap' | 'ecg_segments' = 'feature_importance';
      if (p.modality === 'bloodSmear' || p.modality === 'chestXray') kind = 'heatmap';
      if (p.modality === 'ecg') kind = 'ecg_segments';

      return {
        modelId: p.modelId,
        kind,
        features: kind === 'feature_importance' ? [
          { name: 'Feature A', contribution: 0.4, direction: 'up' },
          { name: 'Feature B', contribution: 0.3, direction: 'up' }
        ] : undefined,
        simulated: true
      };
    });

    const analysisId = fusion.analysisId;
    const flags: RiskFlag[] = buildFlags(analysisId, patientId, fusion);

    const analysis: Analysis = {
      id: analysisId,
      patientId,
      createdAt: new Date().toISOString(),
      inputs: preprocessedInputs,
      predictions,
      fusion,
      explainability,
      uncertainty,
      flags,
      versions: { models: { 'model-clin-v1': '1.0' }, fusion: 'v2.0' }
    };

    globalAnalyses.push(analysis);
    globalFlags.push(...flags);
    
    // Update patient status based on new analysis
    patient.lastAnalysisAt = analysis.createdAt;
    patient.currentRisk = analysis.fusion.overallRisk;

    opts?.onProgress?.('done', 'Complete');
    return analysis;
  }

  async getAnalysis(id: string): Promise<Analysis> {
    const a = globalAnalyses.find(x => x.id === id);
    if (!a) throw new Error('Analysis not found');
    return a;
  }

  async listAnalyses(filters?: any): Promise<Analysis[]> {
    return [...globalAnalyses];
  }

  async getExplainability(analysisId: string): Promise<ExplainabilityResult[]> {
    const a = await this.getAnalysis(analysisId);
    return a.explainability;
  }

  async listModels(): Promise<ModelMetadata[]> {
    return [...MOCK_MODELS];
  }

  async listFlags(): Promise<RiskFlag[]> {
    return [...globalFlags];
  }

  async updateFlag(id: string, action: string, note?: string): Promise<RiskFlag> {
    const flag = globalFlags.find(f => f.id === id);
    if (!flag) throw new Error('Flag not found');
    flag.status = action as any;
    if (action !== 'open') {
      flag.reviewedAt = new Date().toISOString();
      flag.reviewAction = note || action;
    }
    return flag;
  }

  async saveDoctorReview(analysisId: string, review: { status: 'pending' | 'reviewed'; note?: string }): Promise<Analysis> {
    const a = await this.getAnalysis(analysisId);
    a.doctorReview = {
      status: review.status,
      note: review.note,
      reviewedAt: new Date().toISOString()
    };
    return a;
  }
}
