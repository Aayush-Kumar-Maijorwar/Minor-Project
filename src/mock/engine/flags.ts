import { Condition, FusionResult, RiskFlag } from '@/types';

const UPLOAD_HINTS: Record<Condition, string> = {
  tuberculosis: 'a chest X-ray',
  malaria: 'a blood smear',
  leukemia: 'a blood smear',
  diabetes: 'clinical or lab data',
  hypertension: 'clinical data or an ECG'
};

function generateFlagId(): string {
  return `flag-${Math.random().toString(36).substr(2, 9)}`;
}

export function buildFlags(analysisId: string, patientId: string, fusion: FusionResult): RiskFlag[] {
  const flags: RiskFlag[] = [];
  const createdAt = new Date().toISOString();

  for (const result of fusion.perCondition) {
    if (result.riskLevel === 'not_assessed') continue;

    if (result.riskLevel === 'high') {
      flags.push({
        id: generateFlagId(),
        patientId,
        analysisId,
        condition: result.condition,
        severity: 'high',
        reason: `${result.condition} risk is high (fused score: ${result.fusedScore.toFixed(2)}).`,
        createdAt,
        status: 'open'
      });
    }

    if (result.fusedScore > 0.8) {
      flags.push({
        id: generateFlagId(),
        patientId,
        analysisId,
        condition: result.condition,
        severity: 'review_required',
        reason: `${result.condition} fused score ${result.fusedScore.toFixed(2)} exceeds the review threshold. Clinical review required.`,
        createdAt,
        status: 'open'
      });
    }
  }

  if (fusion.notAssessedConditions.length > 0) {
    const details = fusion.notAssessedConditions
      .map(c => `${c} (upload ${UPLOAD_HINTS[c]})`)
      .join(', ');
    flags.push({
      id: generateFlagId(),
      patientId,
      analysisId,
      severity: 'incomplete_data',
      reason: `Not assessed: ${details}.`,
      createdAt,
      status: 'open'
    });
  }

  return flags;
}

export { UPLOAD_HINTS };
