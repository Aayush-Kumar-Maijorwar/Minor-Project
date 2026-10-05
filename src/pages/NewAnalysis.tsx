import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, AlertTriangle } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { usePatients, useAnalyses } from '@/features/hooks';
import { inferenceService } from '@/services/inference';
import { ModalityInput, ModalityType, Analysis } from '@/types';
import { Progress } from '@/components/ui/progress';

const STEPS = [
  'Patient Selection',
  'Input Modalities',
  'Processing & Prediction',
  'Late Fusion',
  'Summary'
];

export default function NewAnalysis() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const { data: patients = [] } = usePatients();
  
  const [selectedPatientId, setSelectedPatientId] = useState<string>('');
  const [inputs, setInputs] = useState<Partial<Record<ModalityType, ModalityInput>>>({
    clinical: { type: 'clinical', status: 'available', source: 'synthetic' },
    lab: { type: 'lab', status: 'available', source: 'synthetic' },
    ecg: { type: 'ecg', status: 'missing', source: 'synthetic' },
    chestXray: { type: 'chestXray', status: 'missing', source: 'synthetic' },
    bloodSmear: { type: 'bloodSmear', status: 'missing', source: 'synthetic' },
  });
  
  const [isRunning, setIsRunning] = useState(false);
  const [progressStage, setProgressStage] = useState('');
  const [analysisResult, setAnalysisResult] = useState<Analysis | null>(null);

  const handleNext = async () => {
    if (step === 1) { // Going to processing
      setIsRunning(true);
      setStep(2);
      try {
        const activeInputs = Object.values(inputs).filter(i => i.status === 'available') as ModalityInput[];
        const result = await inferenceService.runAnalysis(selectedPatientId, activeInputs, {
          onProgress: (stage, detail) => setProgressStage(`${stage}: ${detail}`)
        });
        setAnalysisResult(result);
        setTimeout(() => setStep(3), 1000); // move to fusion visualization after a delay
      } catch (e) {
        console.error(e);
      } finally {
        setIsRunning(false);
      }
    } else {
      setStep(s => s + 1);
    }
  };

  const toggleInput = (type: ModalityType) => {
    setInputs(prev => ({
      ...prev,
      [type]: { ...prev[type]!, status: prev[type]?.status === 'available' ? 'missing' : 'available' }
    }));
  };

  const selectedPatient = patients.find(p => p.id === selectedPatientId);

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
            <div className="space-y-4">
              <p className="text-slate-600">Select an existing synthetic patient to begin.</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {patients.map(p => (
                  <div 
                    key={p.id}
                    onClick={() => setSelectedPatientId(p.id)}
                    className={`p-4 border rounded-lg cursor-pointer transition-colors ${selectedPatientId === p.id ? 'border-teal-600 ring-1 ring-teal-600 bg-teal-50' : 'border-slate-200 hover:border-teal-300 bg-white'}`}
                  >
                    <div className="font-semibold">{p.name}</div>
                    <div className="text-sm text-slate-500">{p.mrn} • {p.age}y</div>
                    <Badge variant="outline" className="mt-2 text-xs">Scenario: {p.scenarioId}</Badge>
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 1 && selectedPatient && (
            <div className="space-y-6">
              <div className="bg-slate-50 p-4 rounded-md flex justify-between items-center">
                <div>
                  <div className="font-semibold">{selectedPatient.name}</div>
                  <div className="text-sm text-slate-500">Select available modalities for this analysis.</div>
                </div>
              </div>
              
              <div className="grid grid-cols-1 gap-4">
                {Object.keys(inputs).map(k => {
                  const type = k as ModalityType;
                  const isAvailable = inputs[type]?.status === 'available';
                  return (
                    <div key={type} className="flex items-center justify-between p-4 border rounded-md">
                      <div className="capitalize font-medium">{type.replace(/([A-Z])/g, ' $1').trim()}</div>
                      <div className="flex items-center space-x-4">
                        <span className="text-sm text-slate-500">{isAvailable ? 'Synthetic Data Attached' : 'Not Provided'}</span>
                        <Button variant={isAvailable ? 'default' : 'outline'} size="sm" onClick={() => toggleInput(type)}>
                          {isAvailable ? 'Mark as Unavailable' : 'Use Synthetic Sample'}
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="flex flex-col items-center justify-center h-[300px] space-y-6">
              <Activity className="w-12 h-12 text-teal-600 animate-pulse" />
              <div className="text-xl font-semibold">Running Analysis Engine</div>
              <div className="text-slate-500">{progressStage || 'Initializing...'}</div>
              {isRunning && <Progress className="w-64" value={undefined} />}
            </div>
          )}

          {step === 3 && analysisResult && (
            <div className="space-y-6 text-center py-12">
              <h3 className="text-xl font-bold">Late Fusion Complete</h3>
              <p className="text-slate-600 max-w-lg mx-auto">
                Models ran independently. Results have been fused using {analysisResult.fusion.modalitiesUsed.length} available modalities.
              </p>
              <div className="flex justify-center space-x-4 pt-6">
                <Badge variant="outline" className="text-sm py-1 px-3">Diabetes: {analysisResult.fusion.perCondition.find(c => c.condition === 'diabetes')?.fusedScore.toFixed(2) || 'N/A'}</Badge>
                <Badge variant="outline" className="text-sm py-1 px-3">Hypertension: {analysisResult.fusion.perCondition.find(c => c.condition === 'hypertension')?.fusedScore.toFixed(2) || 'N/A'}</Badge>
              </div>
            </div>
          )}

          {step === 4 && analysisResult && (
            <div className="space-y-6">
              <div className="p-6 border rounded-lg bg-white shadow-sm text-center">
                <h3 className="text-lg font-medium text-slate-600 mb-2">Overall Patient Risk</h3>
                <div className="text-4xl font-bold mb-4 capitalize">
                  {analysisResult.fusion.overallRisk.replace('_', ' ')}
                </div>
                {analysisResult.flags.length > 0 && (
                  <div className="inline-flex items-center space-x-2 text-amber-600 bg-amber-50 px-3 py-1 rounded-full text-sm font-medium">
                    <AlertTriangle className="w-4 h-4" />
                    <span>{analysisResult.flags.length} Flags Generated</span>
                  </div>
                )}
              </div>
              <p className="text-center text-sm text-slate-500">Analysis has been saved to the patient's history.</p>
            </div>
          )}
          
        </CardContent>
        <CardFooter className="flex justify-between">
          <Button variant="outline" onClick={() => setStep(s => Math.max(0, s - 1))} disabled={step === 0 || isRunning || step > 2}>
            Back
          </Button>
          {step < 4 ? (
            <Button onClick={handleNext} disabled={!selectedPatientId || isRunning || (step === 1 && Object.values(inputs).every(i => i.status !== 'available'))}>
              {step === 1 ? 'Run Analysis' : 'Next'}
            </Button>
          ) : (
            <Button onClick={() => navigate(`/patients/${selectedPatientId}`)}>
              Open Patient Profile
            </Button>
          )}
        </CardFooter>
      </Card>
    </div>
  );
}
