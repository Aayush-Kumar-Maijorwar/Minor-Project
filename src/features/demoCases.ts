import { AnalysisFiles, ClinicalValues, LabValues } from '@/services/inference/InferenceService';

export interface DemoCase {
  id: string;
  title: string;
  description: string;
  patient: { name: string; age: number; sex: 'male' | 'female' | 'other' };
  clinical?: ClinicalValues;
  lab?: LabValues;
  files?: { chestXray?: string; smearCell?: string; smearField?: string; ecg?: string };
  groundTruth?: Record<string, string>;
  note: string;
}

export async function fetchDemoCases(): Promise<DemoCase[]> {
  const resp = await fetch('/demo/demo_cases.json');
  if (!resp.ok) throw new Error('Could not load demo cases (public/demo/demo_cases.json).');
  return resp.json();
}

async function urlToFile(url: string, filename: string): Promise<File> {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Could not load demo asset: ${url}`);
  const blob = await resp.blob();
  return new File([blob], filename, { type: blob.type || 'application/octet-stream' });
}

/** Fetches each referenced demo asset into a real File object, so the normal upload
 * path (validation, previews, multipart submit) is exercised exactly as if the user
 * had picked the file themselves. */
export async function loadDemoCaseFiles(demoCase: DemoCase): Promise<AnalysisFiles> {
  const files: AnalysisFiles = {};
  const f = demoCase.files;
  if (f?.chestXray) files.chestXray = await urlToFile(f.chestXray, 'chest_xray.png');
  if (f?.smearCell) files.smearCell = await urlToFile(f.smearCell, 'smear_cell.png');
  if (f?.smearField) files.smearField = await urlToFile(f.smearField, 'smear_field.png');
  if (f?.ecg) files.ecg = await urlToFile(f.ecg, 'ecg.csv');
  return files;
}
