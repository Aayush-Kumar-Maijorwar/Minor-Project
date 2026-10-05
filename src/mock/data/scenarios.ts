import { Condition } from '@/types';

export interface ScenarioDef {
  id: string;
  name: string;
  description: string;
  latentRisks: Record<Condition, number>; // 0.0 to 1.0 base risk
  clinicalDataOverride?: any;
}

export const scenarios: ScenarioDef[] = [
  {
    id: 'healthy',
    name: 'Healthy / Low-Risk',
    description: 'Patient with normal parameters across all conditions.',
    latentRisks: {
      diabetes: 0.1,
      hypertension: 0.15,
      malaria: 0.05,
      leukemia: 0.02,
      tuberculosis: 0.08
    }
  },
  {
    id: 'diabetes_risk',
    name: 'Diabetes Risk',
    description: 'Patient with elevated fasting glucose and HbA1c.',
    latentRisks: {
      diabetes: 0.85,
      hypertension: 0.4,
      malaria: 0.05,
      leukemia: 0.02,
      tuberculosis: 0.08
    },
    clinicalDataOverride: { fastingGlucose: 155, hba1c: 7.2, bmi: 31 }
  },
  {
    id: 'hypertension_risk',
    name: 'Hypertension Risk',
    description: 'Patient with elevated blood pressure and abnormal ECG patterns.',
    latentRisks: {
      diabetes: 0.3,
      hypertension: 0.88,
      malaria: 0.05,
      leukemia: 0.02,
      tuberculosis: 0.08
    },
    clinicalDataOverride: { systolicBP: 160, diastolicBP: 95 }
  },
  {
    id: 'tb_risk',
    name: 'Possible TB',
    description: 'Patient with symptoms and chest X-ray findings indicative of Tuberculosis.',
    latentRisks: {
      diabetes: 0.1,
      hypertension: 0.2,
      malaria: 0.05,
      leukemia: 0.02,
      tuberculosis: 0.75
    }
  },
  {
    id: 'malaria_risk',
    name: 'Malaria Positive',
    description: 'Blood smear indicates malaria parasites.',
    latentRisks: {
      diabetes: 0.1,
      hypertension: 0.1,
      malaria: 0.92,
      leukemia: 0.02,
      tuberculosis: 0.05
    }
  },
  {
    id: 'leukemia_risk',
    name: 'Leukemia Risk',
    description: 'Blood smear shows abnormal white blood cell patterns.',
    latentRisks: {
      diabetes: 0.1,
      hypertension: 0.1,
      malaria: 0.05,
      leukemia: 0.85,
      tuberculosis: 0.05
    }
  },
  {
    id: 'incomplete_clinical_only',
    name: 'Incomplete: Clinical Only',
    description: 'Patient with only clinical and lab data available, missing imaging.',
    latentRisks: {
      diabetes: 0.6,
      hypertension: 0.7,
      malaria: 0.1,
      leukemia: 0.05,
      tuberculosis: 0.1
    }
  }
];
