import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Activity, AlertTriangle, Upload, X, Sparkles } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { usePatients, useCreatePatient } from '@/features/hooks';
import { inferenceService } from '@/services/inference';
import {
  clinicalFormSchema, labFormSchema, SMOKING_HISTORY_VALUES,
  parseEcgText, validateEcgValues, hasAtLeastOneInput, conditionsAssessableBy
} from '@/features/analysisForm';
import { ClinicalValues, LabValues, AnalysisFiles } from '@/services/inference/InferenceService';
import { fetchDemoCases, loadDemoCaseFiles, DemoCase } from '@/features/demoCases';
import { loadReplay, isNetworkError } from '@/features/replay';
import { LabReportCard } from '@/components/LabReportCard';
import { z } from 'zod';

const formSchema = clinicalFormSchema.merge(labFormSchema);
type FormValues = z.infer<typeof formSchema>;

const STEPS = ['Choose Patient', 'Enter Data', 'Running'];

interface FileSlotDef {
  key: keyof AnalysisFiles;
  label: string;
  help: string;
  accept: string;
}

const FILE_SLOTS: FileSlotDef[] = [
  { key: 'chestXray', label: 'Chest X-ray (TB)', help: 'A frontal chest X-ray image, as in standard TB screening datasets.', accept: 'image/*' },
  { key: 'smearCell', label: 'Blood-smear cell image (malaria)', help: 'Single stained cell crop, as in the NIH malaria dataset.', accept: 'image/*' },
  { key: 'smearField', label: 'Blood-smear field image (leukemia)', help: 'A wider blood-smear field image, not a single-cell crop.', accept: 'image/*' },
  { key: 'ecg', label: 'ECG (one heartbeat)', help: 'A single heartbeat as exactly 187 numbers (.csv, .txt, or .npy).', accept: '.csv,.txt,.npy' }
];

export default function NewAnalysis() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const { data: patients = [] } = usePatients();
  const createPatient = useCreatePatient();

  const [selectedPatientId, setSelectedPatientId] = useState<string>('');
  const [showCreatePatient, setShowCreatePatient] = useState(false);
  const [newPatient, setNewPatient] = useState({ name: '', age: '', sex: 'female' as 'male' | 'female' | 'other' });

  const [demoCases, setDemoCases] = useState<DemoCase[]>([]);
  const [selectedDemoCase, setSelectedDemoCase] = useState<DemoCase | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);

  const [files, setFiles] = useState<Partial<AnalysisFiles>>({});
  const [filePreviews, setFilePreviews] = useState<Partial<Record<keyof AnalysisFiles, string>>>({});
  const [fileErrors, setFileErrors] = useState<Partial<Record<keyof AnalysisFiles, string>>>({});

  const [isRunning, setIsRunning] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const { register, watch, reset, handleSubmit, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    mode: 'onBlur'
  });
  const watched = watch();

  useEffect(() => {
    fetchDemoCases().then(setDemoCases).catch(() => setDemoCases([]));
  }, []);

  useEffect(() => {
    if (!isRunning) return;
    setElapsedSeconds(0);
    const interval = setInterval(() => setElapsedSeconds(s => s + 1), 1000);
    return () => clearInterval(interval);
  }, [isRunning]);

  const selectedPatient = patients.find(p => p.id === selectedPatientId);

  const clinicalValues: Partial<ClinicalValues> = useMemo(() => ({
    age: watched.age, sex: watched.sex, bmi: watched.bmi,
    smokingHistory: watched.smokingHistory, hypertension: watched.hypertension, heartDisease: watched.heartDisease
  }), [watched.age, watched.sex, watched.bmi, watched.smokingHistory, watched.hypertension, watched.heartDisease]);

  const labValues: Partial<LabValues> = useMemo(() => ({
    hba1c: watched.hba1c, bloodGlucose: watched.bloodGlucose
  }), [watched.hba1c, watched.bloodGlucose]);

  const assessable = useMemo(
    () => conditionsAssessableBy({ clinical: clinicalValues, lab: labValues, files }),
    [clinicalValues, labValues, files]
  );

  const handleCreatePatient = async () => {
    const age = Number(newPatient.age);
    if (!newPatient.name.trim() || !age) return;
    const p = await createPatient.mutateAsync({ name: newPatient.name.trim(), age, sex: newPatient.sex });
    setSelectedPatientId(p.id);
    setShowCreatePatient(false);
  };

  const handleLoadDemoCase = async (demoCase: DemoCase) => {
    setDemoLoading(true);
    setFormError(null);
    try {
      setSelectedDemoCase(demoCase);
      if (demoCase.clinical) {
        reset({ ...watch(), ...demoCase.clinical } as FormValues);
      }
      if (demoCase.lab) {
        reset({ ...watch(), ...demoCase.clinical, ...demoCase.lab } as FormValues);
      }
      const loadedFiles = await loadDemoCaseFiles(demoCase);
      setFiles(loadedFiles);
      const previews: Partial<Record<keyof AnalysisFiles, string>> = {};
      (Object.keys(loadedFiles) as (keyof AnalysisFiles)[]).forEach(key => {
        const file = loadedFiles[key];
        if (file && file.type.startsWith('image/')) previews[key] = URL.createObjectURL(file);
      });
      setFilePreviews(previews);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Could not load demo case assets.');
    } finally {
      setDemoLoading(false);
    }
  };

  const handleFileChange = async (key: keyof AnalysisFiles, fileList: FileList | null) => {
    const file = fileList?.[0];
    setFileErrors(prev => ({ ...prev, [key]: undefined }));
    if (!file) {
      setFiles(prev => { const next = { ...prev }; delete next[key]; return next; });
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      setFileErrors(prev => ({ ...prev, [key]: 'File exceeds 15 MB.' }));
      return;
    }
    if (key === 'ecg') {
      const text = await file.text();
      const values = parseEcgText(text);
      const issue = validateEcgValues(values);
      if (issue) {
        setFileErrors(prev => ({ ...prev, [key]: issue }));
        return;
      }
    }
    setFiles(prev => ({ ...prev, [key]: file }));
    if (file.type.startsWith('image/')) {
      setFilePreviews(prev => ({ ...prev, [key]: URL.createObjectURL(file) }));
    }
  };

  const removeFile = (key: keyof AnalysisFiles) => {
    setFiles(prev => { const next = { ...prev }; delete next[key]; return next; });
    setFilePreviews(prev => { const next = { ...prev }; delete next[key]; return next; });
    setFileErrors(prev => ({ ...prev, [key]: undefined }));
  };

  const onSubmit = async (values: FormValues) => {
    setFormError(null);
    const clinical: Partial<ClinicalValues> = {
      age: values.age, sex: values.sex, bmi: values.bmi,
      smokingHistory: values.smokingHistory, hypertension: values.hypertension, heartDisease: values.heartDisease
    };
    const lab: Partial<LabValues> = { hba1c: values.hba1c, bloodGlucose: values.bloodGlucose };
    const clinicalFilled = Object.values(clinical).some(v => v !== undefined);
    const labFilled = Object.values(lab).some(v => v !== undefined);

    if (!hasAtLeastOneInput({ clinical: clinicalFilled ? clinical : undefined, lab: labFilled ? lab : undefined, files })) {
      setFormError('Provide at least one input before running the analysis.');
      return;
    }
    if (Object.values(fileErrors).some(Boolean)) {
      setFormError('Fix the file errors below before running the analysis.');
      return;
    }

    setError(null);
    setIsRunning(true);
    setStep(2);
    try {
      const result = await inferenceService.runAnalysis({
        patientId: selectedPatientId,
        clinical: clinicalFilled ? clinical : undefined,
        lab: labFilled ? lab : undefined,
        files,
        demoCaseId: selectedDemoCase?.id
      });
      navigate(`/analyses/${result.id}`, { state: { analysis: result, files } });
    } catch (e) {
      if (selectedDemoCase && isNetworkError(e)) {
        const replay = await loadReplay(selectedDemoCase.id);
        if (replay) {
          navigate(`/analyses/${replay.analysis.id}`, { state: { analysis: replay.analysis, replay, files } });
          return;
        }
      }
      console.error(e);
      setError(e instanceof Error ? e.message : 'Analysis failed. Please try again.');
      setStep(1);
      setIsRunning(false);
      return;
    }
    setIsRunning(false);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-2xl font-bold text-slate-900">New Analysis</h1>
        <div className="flex space-x-2">
          {STEPS.map((s, idx) => (
            <div key={s} className={`h-2 w-12 rounded-full ${idx <= step ? 'bg-teal-600' : 'bg-slate-200'}`} title={s} />
          ))}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{STEPS[step]}</CardTitle>
        </CardHeader>
        <CardContent className="min-h-[400px]">

          {step === 0 && (
            <div className="space-y-6">
              {formError && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">{formError}</div>
              )}

              <div>
                <p className="text-slate-600 mb-3">Select an existing patient, or create a new one.</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {patients.map(p => (
                    <div
                      key={p.id}
                      onClick={() => setSelectedPatientId(p.id)}
                      className={`p-4 border rounded-lg cursor-pointer transition-colors ${selectedPatientId === p.id ? 'border-teal-600 ring-1 ring-teal-600 bg-teal-50' : 'border-slate-200 hover:border-teal-300 bg-white'}`}
                    >
                      <div className="font-semibold">{p.name}</div>
                      <div className="text-sm text-slate-500">{p.mrn} • {p.age}y</div>
                    </div>
                  ))}
                </div>
                <Button variant="outline" size="sm" className="mt-3" onClick={() => setShowCreatePatient(s => !s)}>
                  + New Patient
                </Button>
                {showCreatePatient && (
                  <div className="mt-3 p-4 border border-slate-200 rounded-md grid grid-cols-1 md:grid-cols-4 gap-3">
                    <input className="border border-slate-200 rounded-md px-3 py-2 text-sm" placeholder="Name"
                      value={newPatient.name} onChange={e => setNewPatient(p => ({ ...p, name: e.target.value }))} />
                    <input type="number" className="border border-slate-200 rounded-md px-3 py-2 text-sm" placeholder="Age"
                      value={newPatient.age} onChange={e => setNewPatient(p => ({ ...p, age: e.target.value }))} />
                    <select className="border border-slate-200 rounded-md px-3 py-2 text-sm" value={newPatient.sex}
                      onChange={e => setNewPatient(p => ({ ...p, sex: e.target.value as any }))}>
                      <option value="female">Female</option>
                      <option value="male">Male</option>
                      <option value="other">Other</option>
                    </select>
                    <Button onClick={handleCreatePatient} disabled={createPatient.isPending}>
                      {createPatient.isPending ? 'Creating…' : 'Create'}
                    </Button>
                  </div>
                )}
              </div>

              {demoCases.length > 0 && (
                <div>
                  <p className="text-slate-600 mb-3 flex items-center"><Sparkles className="w-4 h-4 mr-1.5 text-teal-600" /> Or load a demo case</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {demoCases.map(dc => (
                      <div
                        key={dc.id}
                        onClick={() => handleLoadDemoCase(dc)}
                        className={`p-3 border rounded-lg cursor-pointer transition-colors text-sm ${selectedDemoCase?.id === dc.id ? 'border-teal-600 ring-1 ring-teal-600 bg-teal-50' : 'border-slate-200 hover:border-teal-300 bg-white'}`}
                      >
                        <div className="font-semibold">{dc.title}</div>
                        <div className="text-slate-500 text-xs mt-1">{dc.description}</div>
                      </div>
                    ))}
                  </div>
                  {selectedDemoCase && (
                    <div className="mt-3 bg-amber-50 border border-amber-200 text-amber-800 text-xs px-3 py-2 rounded-md">
                      {selectedDemoCase.note}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {step === 1 && (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">{error}</div>
              )}
              {formError && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">{formError}</div>
              )}

              {assessable.length > 0 && (
                <div className="bg-teal-50 border border-teal-200 text-teal-800 text-sm px-4 py-2 rounded-md">
                  With this you can assess: {assessable.join(', ')}
                </div>
              )}

              <div className="bg-slate-50 p-4 rounded-md">
                <div className="font-semibold">{selectedPatient?.name}</div>
                <div className="text-sm text-slate-500">All sections below are optional - provide at least one.</div>
              </div>

              {/* Clinical */}
              <section className="space-y-3">
                <h3 className="font-semibold text-slate-900">Clinical</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Field label="Age">
                    <input type="number" step="1" className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm" {...register('age', { setValueAs: v => (v === '' || v === undefined) ? undefined : Number(v) })} />
                    {errors.age && <FieldError msg={errors.age.message} />}
                  </Field>
                  <Field label="Sex">
                    <select className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm" {...register('sex', { setValueAs: v => v === '' ? undefined : v })}>
                      <option value="">—</option>
                      <option value="Female">Female</option>
                      <option value="Male">Male</option>
                      <option value="Other">Other</option>
                    </select>
                  </Field>
                  <Field label="BMI (kg/m²)">
                    <input type="number" step="0.1" className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm" {...register('bmi', { setValueAs: v => (v === '' || v === undefined) ? undefined : Number(v) })} />
                    {errors.bmi && <FieldError msg={errors.bmi.message} />}
                  </Field>
                  <Field label="Smoking History">
                    <select className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm" {...register('smokingHistory', { setValueAs: v => v === '' ? undefined : v })}>
                      <option value="">—</option>
                      {SMOKING_HISTORY_VALUES.map(v => <option key={v} value={v}>{v}</option>)}
                    </select>
                  </Field>
                  <Field label="Known Hypertension">
                    <select className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm" {...register('hypertension', { setValueAs: v => v === '' ? undefined : v === 'true' })}>
                      <option value="">—</option>
                      <option value="true">Yes</option>
                      <option value="false">No</option>
                    </select>
                  </Field>
                  <Field label="Known Heart Disease">
                    <select className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm" {...register('heartDisease', { setValueAs: v => v === '' ? undefined : v === 'true' })}>
                      <option value="">—</option>
                      <option value="true">Yes</option>
                      <option value="false">No</option>
                    </select>
                  </Field>
                </div>
              </section>

              {/* Lab */}
              <section className="space-y-3">
                <h3 className="font-semibold text-slate-900">Lab</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Field label="HbA1c (%)">
                    <input type="number" step="0.1" className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm" {...register('hba1c', { setValueAs: v => (v === '' || v === undefined) ? undefined : Number(v) })} />
                    {errors.hba1c && <FieldError msg={errors.hba1c.message} />}
                  </Field>
                  <Field label="Blood Glucose (mg/dL)">
                    <input type="number" step="1" className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm" {...register('bloodGlucose', { setValueAs: v => (v === '' || v === undefined) ? undefined : Number(v) })} />
                    {errors.bloodGlucose && <FieldError msg={errors.bloodGlucose.message} />}
                  </Field>
                </div>
              </section>

              {(labValues.hba1c !== undefined || labValues.bloodGlucose !== undefined || clinicalValues.bmi !== undefined) && (
                <LabReportCard values={{ hba1c: labValues.hba1c, bloodGlucose: labValues.bloodGlucose, bmi: clinicalValues.bmi }} />
              )}

              {/* Files */}
              <section className="space-y-3">
                <h3 className="font-semibold text-slate-900">Files</h3>
                <div className="space-y-3">
                  {FILE_SLOTS.map(slot => (
                    <div key={slot.key} className="p-4 border border-slate-200 rounded-md">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-medium text-sm">{slot.label}</div>
                          <div className="text-xs text-slate-500">{slot.help}</div>
                        </div>
                        {files[slot.key] ? (
                          <Button type="button" variant="outline" size="sm" onClick={() => removeFile(slot.key)}>
                            <X className="w-3.5 h-3.5 mr-1" /> Remove
                          </Button>
                        ) : (
                          <label className="inline-flex items-center px-3 py-1.5 text-xs font-medium border border-slate-200 rounded-md cursor-pointer hover:bg-slate-50">
                            <Upload className="w-3.5 h-3.5 mr-1.5" /> Upload
                            <input type="file" accept={slot.accept} className="hidden"
                              onChange={e => handleFileChange(slot.key, e.target.files)} />
                          </label>
                        )}
                      </div>
                      {filePreviews[slot.key] && (
                        <img src={filePreviews[slot.key]} alt={slot.label} className="mt-3 h-24 w-24 object-cover rounded-md border border-slate-200" />
                      )}
                      {files[slot.key] && !filePreviews[slot.key] && (
                        <div className="mt-2 text-xs text-slate-500">{files[slot.key]!.name}</div>
                      )}
                      {fileErrors[slot.key] && <FieldError msg={fileErrors[slot.key]} />}
                    </div>
                  ))}
                </div>
              </section>

              <button type="submit" className="hidden" />
            </form>
          )}

          {step === 2 && (
            <div className="flex flex-col items-center justify-center h-[300px] space-y-6">
              <Activity className="w-12 h-12 text-teal-600 animate-pulse" />
              <div className="text-xl font-semibold">Running Analysis Engine</div>
              <div className="text-slate-500">{elapsedSeconds}s elapsed</div>
            </div>
          )}

        </CardContent>
        <CardFooter className="flex justify-between">
          <Button variant="outline" onClick={() => setStep(s => Math.max(0, s - 1))} disabled={step === 0 || isRunning}>
            Back
          </Button>
          {step === 0 && (
            <Button onClick={() => setStep(1)} disabled={!selectedPatientId}>Next</Button>
          )}
          {step === 1 && (
            <Button onClick={handleSubmit(onSubmit)} disabled={isRunning}>Run Analysis</Button>
          )}
        </CardFooter>
      </Card>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-600 mb-1">{label}</label>
      {children}
    </div>
  );
}

function FieldError({ msg }: { msg?: string }) {
  if (!msg) return null;
  return <div className="flex items-center text-xs text-red-600 mt-1"><AlertTriangle className="w-3 h-3 mr-1" />{msg}</div>;
}
