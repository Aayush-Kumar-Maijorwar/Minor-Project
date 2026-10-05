import { Condition, FusionResult, FusionConditionResult, FusionContribution, ModelPrediction, ModalityType } from '@/types';


const DEMO_WEIGHTS: Record<Condition, Record<ModalityType, number>> = {
  diabetes: { clinical: 0.5, lab: 0.5, ecg: 0, bloodSmear: 0, chestXray: 0 },
  hypertension: { clinical: 0.4, lab: 0.2, ecg: 0.4, bloodSmear: 0, chestXray: 0 },
  malaria: { clinical: 0, lab: 0, ecg: 0, bloodSmear: 1.0, chestXray: 0 },
  leukemia: { clinical: 0, lab: 0, ecg: 0, bloodSmear: 1.0, chestXray: 0 },
  tuberculosis: { clinical: 0.2, lab: 0, ecg: 0, bloodSmear: 0, chestXray: 0.8 }
};

export function simulateLateFusion(
  predictions: ModelPrediction[], 
  availableModalities: ModalityType[]
): FusionResult {
  const perCondition: FusionConditionResult[] = [];
  const allConditions: Condition[] = ['diabetes', 'hypertension', 'malaria', 'leukemia', 'tuberculosis'];

  let highestRiskScore = 0;
  let dominantCondition: Condition | undefined = undefined;

  for (const condition of allConditions) {
    const conditionWeights = DEMO_WEIGHTS[condition];
    let totalAvailableWeight = 0;
    const contributions: FusionContribution[] = [];

    // Figure out which required modalities are available
    for (const modality of Object.keys(conditionWeights) as ModalityType[]) {
      if (conditionWeights[modality] > 0 && availableModalities.includes(modality)) {
        totalAvailableWeight += conditionWeights[modality];
      }
    }

    if (totalAvailableWeight === 0) {
      perCondition.push({
        condition,
        fusedScore: 0,
        contributions: [],
        riskLevel: 'not_assessed'
      });
      continue;
    }

    let fusedScore = 0;

    for (const pred of predictions.filter(p => p.condition === condition && p.status === 'ok')) {
      const originalWeight = conditionWeights[pred.modality] || 0;
      if (originalWeight > 0) {
        // Re-normalize weight based on available inputs
        const normalizedWeight = originalWeight / totalAvailableWeight;
        fusedScore += pred.score * normalizedWeight;
        contributions.push({
          modality: pred.modality,
          modelId: pred.modelId,
          weight: normalizedWeight,
          score: pred.score
        });
      }
    }

    let riskLevel: 'low' | 'moderate' | 'high' | 'not_assessed' = 'low';
    if (fusedScore > 0.65) riskLevel = 'high';
    else if (fusedScore > 0.35) riskLevel = 'moderate';

    perCondition.push({
      condition,
      fusedScore,
      contributions,
      riskLevel
    });

    if (fusedScore > highestRiskScore) {
      highestRiskScore = fusedScore;
      dominantCondition = condition;
    }
  }

  let overallRisk: 'low' | 'moderate' | 'high' | 'incomplete_data' | 'review_required' = 'low';
  if (highestRiskScore > 0.65) overallRisk = 'high';
  else if (highestRiskScore > 0.35) overallRisk = 'moderate';

  // If very few modalities are available, flag as incomplete
  if (availableModalities.length < 2) {
    overallRisk = 'incomplete_data';
  } else if (highestRiskScore > 0.8) {
    overallRisk = 'review_required';
  }

  const allTypes: ModalityType[] = ['bloodSmear', 'chestXray', 'ecg', 'clinical', 'lab'];
  const excluded = allTypes.filter(t => !availableModalities.includes(t));

  return {
    analysisId: `demo-analysis-${Date.now()}`,
    perCondition,
    overallRisk,
    dominantCondition,
    modalitiesUsed: availableModalities,
    modalitiesExcluded: excluded,
    fusionVersion: 'v2.0-late-fusion-demo',
    simulated: true,
    note: 'Demo weights applied. Unavailable modalities were excluded from this fusion run.'
  };
}
