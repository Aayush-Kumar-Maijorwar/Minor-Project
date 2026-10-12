import { describe, it, expect } from 'vitest';
import { ModelPrediction } from '@/types';
import { simulateLateFusion } from '../lateFusionSim';
import { buildUncertainty } from '../uncertainty';

function pred(overrides: Partial<ModelPrediction>): ModelPrediction {
  return {
    modelId: 'model-x',
    condition: 'diabetes',
    modality: 'clinical',
    score: 0.5,
    label: 'Moderate Risk',
    confidence: 0.5,
    uncertainty: 0.5,
    status: 'ok',
    simulated: true,
    modelVersion: 'v1.0.0-demo',
    ...overrides
  };
}

describe('buildUncertainty', () => {
  it('H: confidence is 0 when there are no predictions', () => {
    const fusion = simulateLateFusion([], []);
    const uncertainty = buildUncertainty([], fusion);
    expect(uncertainty.confidence).toBe(0);
  });

  it('H: confidence equals the mean confidence of ok predictions, ignoring skipped ones', () => {
    const predictions: ModelPrediction[] = [
      pred({ condition: 'diabetes', modality: 'clinical', status: 'ok', confidence: 0.8 }),
      pred({ condition: 'diabetes', modality: 'lab', status: 'ok', confidence: 0.6 }),
      pred({ condition: 'hypertension', modality: 'ecg', status: 'skipped_missing_input', confidence: 0 })
    ];

    const fusion = simulateLateFusion(predictions, ['clinical', 'lab']);
    const uncertainty = buildUncertainty(predictions, fusion);

    expect(uncertainty.confidence).toBeCloseTo(0.7, 5);
  });
});
