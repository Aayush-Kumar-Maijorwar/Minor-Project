import { Condition, FusionResult, Narrative, NarrativeCondition } from '@/types';
import { UPLOAD_HINTS } from './flags';

const DISCLAIMER = 'Decision support from models trained on public datasets; not a diagnosis and not clinically validated.';

function title(condition: Condition): string {
  return condition[0].toUpperCase() + condition.slice(1);
}

function conditionLine(result: FusionResult['perCondition'][number]): string {
  const name = title(result.condition);
  const score = result.fusedScore.toFixed(2);
  if (result.riskLevel === 'high') {
    return `${name}: FLAGGED (score ${score}). Screening support only; clinical correlation recommended.`;
  }
  if (result.riskLevel === 'moderate') {
    return `${name}: BORDERLINE (score ${score}). Close to the flag level; consider clinical correlation.`;
  }
  return `${name}: no indication on the data provided (score ${score}). This does not rule out ${result.condition}.`;
}

/** Simplified mirror of backend/app/narrative.py's template - same facts, same safety rules. */
export function buildNarrative(fusion: FusionResult): Narrative {
  const assessed = fusion.assessedConditions;
  const notAssessed = fusion.notAssessedConditions;
  const flagged = fusion.perCondition.filter(c => c.riskLevel === 'high').map(c => c.condition);

  let headline: string;
  let priority: Narrative['priority'];
  if (assessed.length === 0) {
    headline = 'No condition could be assessed: no usable data was provided.';
    priority = 'incomplete';
  } else if (flagged.length > 0) {
    headline = `Priority: REVIEW. ${flagged.map(title).join(', ')} flagged. ${notAssessed.length} of 5 conditions not assessed.`;
    priority = 'review';
  } else {
    headline = `No condition flagged on the data provided. ${notAssessed.length} of 5 not assessed; this does not rule out disease.`;
    priority = 'routine';
  }

  const conditions: NarrativeCondition[] = fusion.perCondition
    .filter(c => c.riskLevel !== 'not_assessed')
    .map(c => ({ condition: c.condition, level: c.riskLevel, line: conditionLine(c) }));

  const notAssessedText = notAssessed.length > 0
    ? `${notAssessed.map(title).join(', ')}: not assessed (no ${notAssessed.map(c => UPLOAD_HINTS[c]).join(', ')} provided).`
    : '';

  return {
    headline,
    priority,
    conditions,
    notAssessed: notAssessedText,
    disclaimer: DISCLAIMER,
    generatedBy: 'template'
  };
}
