// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import AnalysisResult from '../AnalysisResult';
import { Analysis } from '@/types';

vi.mock('@/services/inference', () => ({
  inferenceService: {
    getHealth: vi.fn().mockResolvedValue({ status: 'ok', models: [], versions: {}, llmEnabled: false }),
    getAnalysis: vi.fn(),
    regenerateNarrative: vi.fn()
  }
}));

function buildAnalysis(): Analysis {
  return {
    id: 'AN-1',
    patientId: 'PT-1',
    createdAt: new Date().toISOString(),
    inputs: [],
    predictions: [],
    fusion: {
      analysisId: 'AN-1',
      perCondition: [
        { condition: 'tuberculosis', fusedScore: 0.71, riskLevel: 'high', contributions: [{ modality: 'chestXray', modelId: 'tb-x', weight: 1, score: 0.71, threshold: 0.42 }] },
        { condition: 'malaria', fusedScore: 0, riskLevel: 'not_assessed', contributions: [] },
        { condition: 'leukemia', fusedScore: 0, riskLevel: 'not_assessed', contributions: [] },
        { condition: 'diabetes', fusedScore: 0, riskLevel: 'not_assessed', contributions: [] },
        { condition: 'hypertension', fusedScore: 0, riskLevel: 'not_assessed', contributions: [] }
      ],
      overallRisk: 'high',
      modalitiesUsed: ['chestXray'],
      modalitiesExcluded: ['lab', 'clinical', 'ecg', 'bloodSmearCell', 'bloodSmearField'],
      assessedConditions: ['tuberculosis'],
      notAssessedConditions: ['malaria', 'leukemia', 'diabetes', 'hypertension'],
      fusionVersion: 'v1',
      simulated: false,
      note: ''
    },
    explainability: [],
    uncertainty: {
      confidence: 0.8, uncertaintyLevel: 'low', reliability: 'limited',
      dataCompleteness: { available: 1, total: 5, missing: [] }, modelStatus: 'ok', messages: []
    },
    flags: [],
    versions: { models: {}, fusion: 'v1' },
    narrative: {
      headline: 'Priority: REVIEW. Tuberculosis flagged. 4 of 5 conditions not assessed.',
      priority: 'review',
      conditions: [
        { condition: 'tuberculosis', level: 'high', line: 'Tuberculosis: FLAGGED (score 0.71, flag threshold 0.42).' }
      ],
      notAssessed: 'Malaria, Leukemia, Diabetes, Hypertension: not assessed.',
      disclaimer: 'Decision support only; not a diagnosis.',
      generatedBy: 'template'
    },
    submittedValues: { clinical: null, lab: null }
  };
}

function renderWithState(analysis: Analysis) {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[{ pathname: `/analyses/${analysis.id}`, state: { analysis } }]}>
        <Routes>
          <Route path="/analyses/:id" element={<AnalysisResult />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('AnalysisResult', () => {
  beforeEach(() => {
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
  });

  afterEach(() => cleanup());

  it('renders the narrative headline and per-condition line', async () => {
    renderWithState(buildAnalysis());
    expect(await screen.findByText(/Priority: REVIEW\. Tuberculosis flagged\./)).toBeTruthy();
    expect(screen.getByText(/Tuberculosis: FLAGGED \(score 0\.71, flag threshold 0\.42\)\./)).toBeTruthy();
  });

  it('shows not_assessed conditions as their own grey "Not assessed" state, never a positive colour', async () => {
    renderWithState(buildAnalysis());
    await screen.findByText(/Priority: REVIEW/);

    const notAssessedBadges = screen.getAllByText('Not assessed');
    expect(notAssessedBadges.length).toBe(4); // malaria, leukemia, diabetes, hypertension

    for (const badge of notAssessedBadges) {
      const pill = badge.closest('div');
      expect(pill?.className).toMatch(/slate/);
      expect(pill?.className).not.toMatch(/green/);
      expect(pill?.className).not.toMatch(/teal/);
      expect(pill?.className).not.toMatch(/red/);
    }

    // And each not_assessed card tells the user what to add next.
    expect(screen.getByText(/Add a blood-smear cell image to check malaria\./)).toBeTruthy();
  });

  it('copy summary contains the headline, every narrative line, and the disclaimer', async () => {
    renderWithState(buildAnalysis());
    await screen.findByText(/Priority: REVIEW/);

    fireEvent.click(screen.getByText('Copy summary'));

    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
    const copied = (navigator.clipboard.writeText as any).mock.calls[0][0] as string;
    expect(copied).toContain('Priority: REVIEW. Tuberculosis flagged. 4 of 5 conditions not assessed.');
    expect(copied).toContain('Tuberculosis: FLAGGED (score 0.71, flag threshold 0.42).');
    expect(copied).toContain('Decision support only; not a diagnosis.');
  });

  it('disables "Simplify wording (AI)" when the backend reports llmEnabled: false', async () => {
    renderWithState(buildAnalysis());
    const button = await screen.findByText(/Simplify wording/);
    expect(button.closest('button')?.disabled).toBe(true);
  });

  it('shows the diabetes strategyUsed and which models were excluded', async () => {
    const analysis = buildAnalysis();
    analysis.fusion.perCondition[3] = {
      condition: 'diabetes', fusedScore: 0.8, riskLevel: 'high',
      contributions: [{ modality: 'clinicalLab', modelId: 'diabetes_combined', weight: 1, score: 0.9, threshold: 0.4 }],
      strategyUsed: 'combined', notUsedModelIds: ['diabetes_lab', 'diabetes_clinical']
    };
    analysis.fusion.assessedConditions = ['tuberculosis', 'diabetes'];
    analysis.fusion.notAssessedConditions = ['malaria', 'leukemia', 'hypertension'];
    analysis.narrative!.conditions.push({ condition: 'diabetes', level: 'high', line: 'Diabetes: FLAGGED.' });

    renderWithState(analysis);
    await screen.findByText(/Priority: REVIEW/);
    expect(screen.getByText(/Used the combined lab \+ clinical model/)).toBeTruthy();
    expect(screen.getByText(/not used: diabetes_lab, diabetes_clinical/)).toBeTruthy();
  });

  it('toggles a raw-JSON view of the analysis response', async () => {
    renderWithState(buildAnalysis());
    await screen.findByText(/Priority: REVIEW/);

    expect(screen.queryByText(/"id": "AN-1"/)).toBeNull();
    fireEvent.click(screen.getByText('Raw response (JSON)'));
    expect(screen.getByText(/"id": "AN-1"/)).toBeTruthy();
  });
});
