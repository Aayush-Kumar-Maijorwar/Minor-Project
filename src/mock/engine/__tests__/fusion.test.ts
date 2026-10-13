import { describe, it, expect } from 'vitest';
import { ModalityInput, ModalityType, Condition } from '@/types';
import { simulateModalityPredictions } from '../modalityModelSim';
import { MODELS } from '../modalityModelSim';
import { simulateLateFusion, DEMO_WEIGHTS } from '../lateFusionSim';
import { buildFlags } from '../flags';
import { scenarios } from '../../data/scenarios';

const ALL_TYPES: ModalityType[] = ['bloodSmearCell', 'bloodSmearField', 'chestXray', 'ecg', 'clinical', 'lab'];
const ALL_CONDITIONS: Condition[] = ['diabetes', 'hypertension', 'malaria', 'leukemia', 'tuberculosis'];

function buildInputs(available: ModalityType[]): ModalityInput[] {
  return ALL_TYPES.map(type => ({
    type,
    status: available.includes(type) ? 'available' : 'missing',
    source: 'synthetic'
  }));
}

function runScenario(patientId: string, scenarioId: string, available: ModalityType[]) {
  const inputs = buildInputs(available);
  const predictions = simulateModalityPredictions(patientId, inputs, scenarioId);
  const fusion = simulateLateFusion(predictions, available);
  return { predictions, fusion };
}

describe('simulateLateFusion - false negative fixes', () => {
  it('A: clinical+lab only (healthy) never shows TB as low; TB/malaria/leukemia not_assessed, diabetes/hypertension assessed', () => {
    const { fusion } = runScenario('p-a', 'healthy', ['clinical', 'lab']);

    const byCondition = (c: Condition) => fusion.perCondition.find(r => r.condition === c)!;

    expect(byCondition('tuberculosis').riskLevel).toBe('not_assessed');
    expect(byCondition('tuberculosis').riskLevel).not.toBe('low');
    expect(byCondition('malaria').riskLevel).toBe('not_assessed');
    expect(byCondition('leukemia').riskLevel).toBe('not_assessed');

    expect(byCondition('diabetes').riskLevel).not.toBe('not_assessed');
    expect(byCondition('hypertension').riskLevel).not.toBe('not_assessed');

    expect(fusion.notAssessedConditions.sort()).toEqual(['leukemia', 'malaria', 'tuberculosis'].sort());
    expect(fusion.assessedConditions.sort()).toEqual(['diabetes', 'hypertension'].sort());
  });

  it('B: lab only - hypertension not_assessed, diabetes assessed', () => {
    const { fusion } = runScenario('p-b', 'healthy', ['lab']);
    const byCondition = (c: Condition) => fusion.perCondition.find(r => r.condition === c)!;

    expect(byCondition('hypertension').riskLevel).toBe('not_assessed');
    expect(byCondition('diabetes').riskLevel).not.toBe('not_assessed');
  });

  it('C: chestXray only (tb_risk) shows TB high, overall high (not incomplete_data), and flags include a high TB flag plus an incomplete_data flag', () => {
    const { fusion } = runScenario('p-c', 'tb_risk', ['chestXray']);
    const tb = fusion.perCondition.find(r => r.condition === 'tuberculosis')!;

    expect(tb.riskLevel).toBe('high');
    expect(fusion.overallRisk).toBe('high');
    expect(fusion.overallRisk).not.toBe('incomplete_data');

    const flags = buildFlags(fusion.analysisId, 'p-c', fusion);
    const tbFlag = flags.find(f => f.condition === 'tuberculosis' && f.severity === 'high');
    expect(tbFlag).toBeTruthy();

    const incompleteFlags = flags.filter(f => f.severity === 'incomplete_data');
    expect(incompleteFlags.length).toBe(1);
  });

  it('D: no modalities available - overallRisk incomplete_data, all five not_assessed', () => {
    const { fusion } = runScenario('p-d', 'healthy', []);

    expect(fusion.overallRisk).toBe('incomplete_data');
    expect(fusion.assessedConditions.length).toBe(0);
    expect(fusion.notAssessedConditions.sort()).toEqual([...ALL_CONDITIONS].sort());
  });

  it('E: all five modalities (healthy) - five assessed, overall low, no incomplete_data flag', () => {
    const { fusion } = runScenario('p-e', 'healthy', ALL_TYPES);

    expect(fusion.assessedConditions.length).toBe(5);
    expect(fusion.notAssessedConditions.length).toBe(0);
    expect(fusion.overallRisk).toBe('low');

    const flags = buildFlags(fusion.analysisId, 'p-e', fusion);
    expect(flags.some(f => f.severity === 'incomplete_data')).toBe(false);
  });

  it('F: contribution weights re-normalize to sum to 1.0 for every assessed condition', () => {
    const combos: [string, ModalityType[]][] = [
      ['healthy', ['clinical', 'lab']],
      ['healthy', ['lab']],
      ['tb_risk', ['chestXray']],
      ['healthy', ALL_TYPES],
      ['hypertension_risk', ['clinical', 'ecg']]
    ];

    for (const [scenarioId, available] of combos) {
      const { fusion } = runScenario('p-f', scenarioId, available);
      for (const result of fusion.perCondition) {
        if (result.riskLevel === 'not_assessed') continue;
        const weightSum = result.contributions.reduce((sum, c) => sum + c.weight, 0);
        expect(weightSum).toBeCloseTo(1.0, 5);
      }
    }
  });

  it('G: every DEMO_WEIGHTS entry with weight > 0 corresponds to a (condition, modality) pair MODELS actually produces', () => {
    for (const condition of ALL_CONDITIONS) {
      const weights = DEMO_WEIGHTS[condition];
      for (const modality of Object.keys(weights) as ModalityType[]) {
        if (weights[modality] > 0) {
          const producesIt = MODELS[modality].targets.includes(condition);
          expect(producesIt, `${condition} <- ${modality} has weight but no model produces it`).toBe(true);
        }
      }
    }
  });

  it('sanity: scenarios used above exist', () => {
    expect(scenarios.find(s => s.id === 'healthy')).toBeTruthy();
    expect(scenarios.find(s => s.id === 'tb_risk')).toBeTruthy();
  });
});
