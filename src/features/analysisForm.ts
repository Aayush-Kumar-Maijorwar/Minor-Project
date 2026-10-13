import { z } from 'zod';
import { AnalysisFiles, ClinicalValues, LabValues } from '@/services/inference/InferenceService';

export const SMOKING_HISTORY_VALUES = ['never', 'former', 'current', 'not current', 'ever', 'No Info'] as const;

// Same ranges as backend/app/validation.py - the frontend form rejects obviously bad
// values before submit, but the backend is still the source of truth (safety rule 1).
export const clinicalFormSchema = z.object({
  age: z.coerce.number().min(0, 'Age must be 0 or more').max(120, 'Age must be 120 or less').optional(),
  sex: z.enum(['Female', 'Male', 'Other']).optional(),
  bmi: z.coerce.number().min(10, 'BMI must be 10 or more').max(70, 'BMI must be 70 or less').optional(),
  smokingHistory: z.enum(SMOKING_HISTORY_VALUES).optional(),
  hypertension: z.boolean().optional(),
  heartDisease: z.boolean().optional()
});

export const labFormSchema = z.object({
  hba1c: z.coerce.number().min(3, 'HbA1c must be 3 or more').max(15, 'HbA1c must be 15 or less').optional(),
  bloodGlucose: z.coerce.number().min(40, 'Blood glucose must be 40 or more').max(600, 'Blood glucose must be 600 or less').optional()
});

export type ClinicalFormValues = z.infer<typeof clinicalFormSchema>;
export type LabFormValues = z.infer<typeof labFormSchema>;

export const ECG_REQUIRED_LENGTH = 187;

/** Parses a .csv/.txt heartbeat (any common delimiter) into numbers. */
export function parseEcgText(text: string): number[] {
  return text
    .split(/[,\s;]+/)
    .map(s => s.trim())
    .filter(s => s.length > 0)
    .map(Number);
}

export function validateEcgValues(values: number[]): string | null {
  if (values.length === 0) return 'Could not read any numbers from this file.';
  if (values.some(v => Number.isNaN(v))) return 'This file contains non-numeric values.';
  if (values.length !== ECG_REQUIRED_LENGTH) {
    return `ECG must be a single ${ECG_REQUIRED_LENGTH}-sample heartbeat (found ${values.length} values).`;
  }
  return null;
}

function hasDefinedValue(obj: Record<string, unknown> | undefined): boolean {
  if (!obj) return false;
  return Object.values(obj).some(v => v !== undefined && v !== null && v !== '');
}

export interface AnalysisFormState {
  clinical?: Partial<ClinicalValues>;
  lab?: Partial<LabValues>;
  files?: Partial<AnalysisFiles>;
}

export function hasAtLeastOneInput(form: AnalysisFormState): boolean {
  const clinicalFilled = hasDefinedValue(form.clinical as Record<string, unknown> | undefined);
  const labFilled = hasDefinedValue(form.lab as Record<string, unknown> | undefined);
  const filesFilled = !!form.files && Object.values(form.files).some(Boolean);
  return clinicalFilled || labFilled || filesFilled;
}

/** What each filled-in section lets the backend assess, for the "With this you can
 * assess: ..." hint. Mirrors backend/app/main.py's CLINICAL_MODEL_FIELDS / FILE_SLOTS. */
export function conditionsAssessableBy(form: AnalysisFormState): string[] {
  const conditions = new Set<string>();
  const clinical = form.clinical as Record<string, unknown> | undefined;
  if (clinical?.age !== undefined && clinical?.bmi !== undefined && clinical?.smokingHistory !== undefined
    && clinical?.hypertension !== undefined && clinical?.heartDisease !== undefined && clinical?.sex !== undefined) {
    conditions.add('Diabetes');
  }
  if (clinical?.age !== undefined && clinical?.bmi !== undefined && clinical?.smokingHistory !== undefined
    && clinical?.heartDisease !== undefined && clinical?.sex !== undefined) {
    conditions.add('Hypertension');
  }
  const lab = form.lab as Record<string, unknown> | undefined;
  if (lab?.hba1c !== undefined && lab?.bloodGlucose !== undefined) conditions.add('Diabetes');
  if (form.files?.chestXray) conditions.add('Tuberculosis');
  if (form.files?.smearCell) conditions.add('Malaria');
  if (form.files?.smearField) conditions.add('Leukemia');
  if (form.files?.ecg) conditions.add('Hypertension');
  return Array.from(conditions);
}
