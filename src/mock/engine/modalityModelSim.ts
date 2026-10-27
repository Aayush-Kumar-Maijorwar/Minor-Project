import { Condition, ModalityInput, ModalityType, ModelPrediction } from '@/types';
import { generateSeed, createSeededRandom } from './seededRandom';
import { scenarios } from '../data/scenarios';

export const MODELS: Record<ModalityType, { id: string; name: string; targets: Condition[] }> = {
  bloodSmearCell: { id: 'model-smear-cell-v1', name: 'Blood Smear Cell Analysis Model', targets: ['malaria'] },
  bloodSmearField: { id: 'model-smear-field-v1', name: 'Blood Smear Field Analysis Model', targets: ['leukemia'] },
  chestXray: { id: 'model-cxr-v2', name: 'CXR Pathology Model', targets: ['tuberculosis'] },
  ecg: { id: 'model-ecg-v1', name: 'ECG Biomarker Model', targets: ['hypertension'] },
  clinical: { id: 'model-clin-v1', name: 'Clinical Data Model', targets: ['diabetes', 'hypertension'] },
  lab: { id: 'model-lab-v1', name: 'Laboratory Data Model', targets: ['diabetes'] },
  // Mock mode has no combined-model simulation (see lateFusionSim.ts's DEMO_WEIGHTS) -
  // targets is empty so this entry never actually fires in simulateModalityPredictions.
  clinicalLab: { id: 'model-combined-v1', name: 'Combined Lab + Clinical Model', targets: [] }
};

export function simulateModalityPredictions(patientId: string, inputs: ModalityInput[], scenarioId: string): ModelPrediction[] {
  const scenario = scenarios.find(s => s.id === scenarioId) || scenarios[0];
  const predictions: ModelPrediction[] = [];
  
  const activeModalities = inputs.filter(i => i.status === 'available').map(i => i.type);
  const seed = generateSeed(patientId, activeModalities);
  const random = createSeededRandom(seed);

  for (const input of inputs) {
    const modelInfo = MODELS[input.type];
    if (!modelInfo) continue;

    for (const target of modelInfo.targets) {
      if (input.status === 'available') {
        // Base risk + small noise (-0.05 to +0.05)
        let score = scenario.latentRisks[target] + (random() * 0.1 - 0.05);
        score = Math.max(0, Math.min(1, score)); // clamp 0-1
        
        let label = 'Normal';
        if (score > 0.65) label = 'High Risk';
        else if (score > 0.35) label = 'Moderate Risk';

        // Confidence: higher at extremes, lower in middle
        const distFromCenter = Math.abs(score - 0.5);
        const confidence = 0.60 + (distFromCenter * 0.8) * (0.9 + random() * 0.1);

        predictions.push({
          modelId: modelInfo.id,
          condition: target,
          modality: input.type,
          score,
          label,
          confidence: Math.min(0.99, confidence),
          uncertainty: 1 - confidence,
          status: 'ok',
          simulated: true,
          modelVersion: 'v1.0.0-demo'
        });
      } else {
        predictions.push({
          modelId: modelInfo.id,
          condition: target,
          modality: input.type,
          score: 0,
          label: 'Not Assessed',
          confidence: 0,
          uncertainty: 1,
          status: 'skipped_missing_input',
          simulated: true,
          modelVersion: 'v1.0.0-demo'
        });
      }
    }
  }

  return predictions;
}
