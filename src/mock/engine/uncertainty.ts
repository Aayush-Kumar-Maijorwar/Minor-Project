import { ModalityType, ModelPrediction, FusionResult, UncertaintyResult } from '@/types';
import { DEMO_WEIGHTS } from './lateFusionSim';

function requiredModalities(condition: keyof typeof DEMO_WEIGHTS): ModalityType[] {
  const weights = DEMO_WEIGHTS[condition];
  return (Object.keys(weights) as ModalityType[]).filter(m => weights[m] > 0);
}

export function buildUncertainty(predictions: ModelPrediction[], fusion: FusionResult): UncertaintyResult {
  const okPredictions = predictions.filter(p => p.status === 'ok');
  const confidence = okPredictions.length > 0
    ? okPredictions.reduce((sum, p) => sum + p.confidence, 0) / okPredictions.length
    : 0;

  const assessedCount = fusion.assessedConditions.length;
  const reliability: 'adequate' | 'limited' | 'low' =
    assessedCount === 5 ? 'adequate' : assessedCount >= 3 ? 'limited' : 'low';

  const uncertaintyLevel: 'low' | 'moderate' | 'high' =
    confidence >= 0.75 ? 'low' : confidence >= 0.5 ? 'moderate' : 'high';

  const missing = Array.from(new Set(
    fusion.notAssessedConditions.flatMap(requiredModalities)
  ));

  return {
    confidence,
    uncertaintyLevel,
    reliability,
    dataCompleteness: {
      available: fusion.modalitiesUsed.length,
      total: 5,
      missing
    },
    modelStatus: 'Demo Mode Simulation',
    messages: [
      'Confidence reflects model agreement in Demo Mode and is not medical certainty.',
      'Unavailable modalities were excluded from this fusion run.'
    ]
  };
}
