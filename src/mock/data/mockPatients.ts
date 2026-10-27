import { Patient } from '@/types';
import { scenarios } from './scenarios';

export const mockPatients: Patient[] = [
  {
    id: 'DEMO-0001',
    mrn: 'MRN-847291',
    name: 'Robert Chen (Synthetic)',
    age: 45,
    sex: 'male',
    scenarioId: 'healthy',
    status: 'active',
    lastAnalysisAt: '2026-10-01T10:00:00Z',
    currentRisk: 'low',
    availableModalities: ['clinical', 'lab', 'ecg', 'bloodSmearCell', 'bloodSmearField', 'chestXray']
  },
  {
    id: 'DEMO-0002',
    mrn: 'MRN-192837',
    name: 'Sarah Jenkins (Synthetic)',
    age: 58,
    sex: 'female',
    scenarioId: 'diabetes_risk',
    status: 'active',
    lastAnalysisAt: '2026-10-02T14:30:00Z',
    currentRisk: 'high',
    availableModalities: ['clinical', 'lab']
  },
  {
    id: 'DEMO-0003',
    mrn: 'MRN-564738',
    name: 'James Wilson (Synthetic)',
    age: 62,
    sex: 'male',
    scenarioId: 'hypertension_risk',
    status: 'active',
    lastAnalysisAt: '2026-10-03T09:15:00Z',
    currentRisk: 'high',
    availableModalities: ['clinical', 'lab', 'ecg']
  },
  {
    id: 'DEMO-0004',
    mrn: 'MRN-998877',
    name: 'Maria Garcia (Synthetic)',
    age: 34,
    sex: 'female',
    scenarioId: 'tb_risk',
    status: 'active',
    lastAnalysisAt: '2026-10-04T11:45:00Z',
    currentRisk: 'moderate',
    availableModalities: ['clinical', 'chestXray']
  },
  {
    id: 'DEMO-0005',
    mrn: 'MRN-112233',
    name: 'David Osei (Synthetic)',
    age: 28,
    sex: 'male',
    scenarioId: 'malaria_risk',
    status: 'active',
    lastAnalysisAt: '2026-10-05T08:20:00Z',
    currentRisk: 'high',
    availableModalities: ['clinical', 'bloodSmearCell']
  },
  {
    id: 'DEMO-0006',
    mrn: 'MRN-445566',
    name: 'Emily Davis (Synthetic)',
    age: 12,
    sex: 'female',
    scenarioId: 'leukemia_risk',
    status: 'active',
    lastAnalysisAt: '2026-10-05T16:00:00Z',
    currentRisk: 'high',
    availableModalities: ['clinical', 'lab', 'bloodSmearField']
  },
  {
    id: 'DEMO-0007',
    mrn: 'MRN-778899',
    name: 'Michael Chang (Synthetic)',
    age: 50,
    sex: 'male',
    scenarioId: 'incomplete_clinical_only',
    status: 'active',
    lastAnalysisAt: '2026-10-06T07:30:00Z',
    currentRisk: 'review_required',
    availableModalities: ['clinical', 'lab']
  }
];

export function getMockPatient(id: string): Patient | undefined {
  return mockPatients.find(p => p.id === id);
}
