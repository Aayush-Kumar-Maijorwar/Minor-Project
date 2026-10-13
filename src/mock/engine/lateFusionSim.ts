import { Condition, FusionResult, FusionConditionResult, FusionContribution, ModelPrediction, ModalityType } from '@/types';


export const DEMO_WEIGHTS: Record<Condition, Record<ModalityType, number>> = {
  diabetes: { clinical: 0.5, lab: 0.5, ecg: 0, bloodSmearCell: 0, bloodSmearField: 0, chestXray: 0 },
  hypertension: { clinical: 0.5, lab: 0, ecg: 0.5, bloodSmearCell: 0, bloodSmearField: 0, chestXray: 0 },
  malaria: { clinical: 0, lab: 0, ecg: 0, bloodSmearCell: 1.0, bloodSmearField: 0, chestXray: 0 },
  leukemia: { clinical: 0, lab: 0, ecg: 0, bloodSmearCell: 0, bloodSmearField: 1.0, chestXray: 0 },
  tuberculosis: { clinical: 0, lab: 0, ecg: 0, bloodSmearCell: 0, bloodSmearField: 0, chestXray: 1.0 }
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

    // A condition is only assessed if at least one 'ok' prediction with a
    // non-zero weight actually exists for it (not merely "weight is defined").
    const okPredictions = predictions.filter(
      p => p.condition === condition && p.status === 'ok' && (conditionWeights[p.modality] || 0) > 0
    );

    if (okPredictions.length === 0) {
      perCondition.push({
        condition,
        fusedScore: 0,
        contributions: [],
        riskLevel: 'not_assessed'
      });
      continue;
    }

    const totalAvailableWeight = okPredictions.reduce((sum, pred) => sum + conditionWeights[pred.modality], 0);

    let fusedScore = 0;
    const contributions: FusionContribution[] = [];

    for (const pred of okPredictions) {
      const originalWeight = conditionWeights[pred.modality];
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

  const assessedConditions = perCondition.filter(c => c.riskLevel !== 'not_assessed').map(c => c.condition);
  const notAssessedConditions = allConditions.filter(c => !assessedConditions.includes(c));

  let overallRisk: 'low' | 'moderate' | 'high' | 'incomplete_data' | 'review_required';
  if (assessedConditions.length === 0) {
    // No condition could be assessed at all - missing data must never be
    // reported as a real (low) risk level.
    overallRisk = 'incomplete_data';
  } else if (highestRiskScore > 0.8) {
    overallRisk = 'review_required';
  } else if (highestRiskScore > 0.65) {
    overallRisk = 'high';
  } else if (highestRiskScore > 0.35) {
    overallRisk = 'moderate';
  } else {
    overallRisk = 'low';
  }

  const allTypes: ModalityType[] = ['bloodSmearCell', 'bloodSmearField', 'chestXray', 'ecg', 'clinical', 'lab'];
  const excluded = allTypes.filter(t => !availableModalities.includes(t));

  return {
    analysisId: `demo-analysis-${Date.now()}`,
    perCondition,
    overallRisk,
    dominantCondition,
    modalitiesUsed: availableModalities,
    modalitiesExcluded: excluded,
    assessedConditions,
    notAssessedConditions,
    fusionVersion: 'v2.0-late-fusion-demo',
    simulated: true,
    note: `Demo weights applied. ${assessedConditions.length} of ${allConditions.length} conditions assessed; unavailable modalities excluded those conditions from this fusion run.`
  };
}
