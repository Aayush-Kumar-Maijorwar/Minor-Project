import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { LineChart, Line, ResponsiveContainer, YAxis } from 'recharts';
import {
  AlertTriangle, CheckCircle2, HelpCircle, AlertCircle, ChevronDown, ChevronUp,
  Printer, Copy, Sparkles, Code
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { LabReportCard } from '@/components/LabReportCard';
import { inferenceService } from '@/services/inference';
import { useBackendStatus, isFakeHealth } from '@/features/useBackendStatus';
import { Analysis, Condition, FusionConditionResult, Narrative } from '@/types';
import { AnalysisFiles } from '@/services/inference/InferenceService';
import { ReplayRecord } from '@/features/replay';
import { parseEcgText } from '@/features/analysisForm';

const CONDITION_ORDER: Condition[] = ['tuberculosis', 'malaria', 'leukemia', 'diabetes', 'hypertension'];
const CONDITION_LABELS: Record<Condition, string> = {
  tuberculosis: 'Tuberculosis', malaria: 'Malaria', leukemia: 'Leukemia', diabetes: 'Diabetes', hypertension: 'Hypertension'
};
const UPLOAD_HINTS: Record<Condition, string> = {
  tuberculosis: 'Add a chest X-ray to check tuberculosis.',
  malaria: 'Add a blood-smear cell image to check malaria.',
  leukemia: 'Add a blood-smear field image to check leukemia.',
  diabetes: 'Add clinical or lab data to check diabetes.',
  hypertension: 'Add clinical data or an ECG to check hypertension.'
};

const LEVEL_DISPLAY: Record<string, { word: string; icon: React.ElementType; color: string; bg: string }> = {
  high: { word: 'Flagged for review', icon: AlertTriangle, color: 'text-red-700', bg: 'bg-red-50 border-red-200' },
  moderate: { word: 'Borderline', icon: AlertCircle, color: 'text-amber-700', bg: 'bg-amber-50 border-amber-200' },
  low: { word: 'No indication', icon: CheckCircle2, color: 'text-teal-700', bg: 'bg-teal-50 border-teal-200' },
  not_assessed: { word: 'Not assessed', icon: HelpCircle, color: 'text-slate-500', bg: 'bg-slate-50 border-slate-200' }
};

const STRATEGY_LABELS: Record<string, string> = {
  combined: 'Used the combined lab + clinical model',
  fusion: 'Used the lab + clinical fusion',
  lab_only: 'Used the lab model only',
  clinical_only: 'Used the clinical model only',
};

const PRIORITY_DISPLAY: Record<string, { word: string; icon: React.ElementType; color: string }> = {
  review: { word: 'REVIEW', icon: AlertTriangle, color: 'text-red-700' },
  routine: { word: 'ROUTINE', icon: CheckCircle2, color: 'text-teal-700' },
  incomplete: { word: 'INCOMPLETE', icon: HelpCircle, color: 'text-slate-500' }
};

interface NavState {
  analysis?: Analysis;
  files?: Partial<AnalysisFiles>;
  replay?: ReplayRecord;
}

function Gauge({ score, threshold, label }: { score: number; threshold: number; label?: string }) {
  const pct = Math.round(Math.min(1, Math.max(0, score)) * 100);
  const thrPct = Math.round(Math.min(1, Math.max(0, threshold)) * 100);
  const over = score >= threshold;
  return (
    <div className="space-y-1">
      {label && <div className="text-xs text-slate-500">{label}</div>}
      <div className="relative h-3 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full ${over ? 'bg-red-400' : 'bg-teal-400'}`} style={{ width: `${pct}%` }} />
        <div className="absolute top-0 bottom-0 w-0.5 bg-slate-700" style={{ left: `${thrPct}%` }} title={`Flag threshold ${threshold.toFixed(2)}`} />
      </div>
      <div className="flex justify-between text-[11px] text-slate-400">
        <span>score {score.toFixed(2)}</span>
        <span>threshold {threshold.toFixed(2)}</span>
      </div>
    </div>
  );
}

function ConditionCard({ result, narrative, explainability }: {
  result: FusionConditionResult;
  narrative?: Narrative['conditions'][number];
  explainability: Analysis['explainability'];
}) {
  const [expanded, setExpanded] = useState(false);
  const display = LEVEL_DISPLAY[result.riskLevel];
  const Icon = display.icon;

  return (
    <Card className={result.riskLevel === 'not_assessed' ? 'opacity-90' : ''}>
      <CardContent className="p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="font-semibold text-slate-900">{CONDITION_LABELS[result.condition]}</div>
          <div className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${display.bg} ${display.color}`}>
            <Icon className="w-3.5 h-3.5 mr-1.5" />
            {display.word}
          </div>
        </div>

        {result.riskLevel === 'not_assessed' ? (
          <p className="text-sm text-slate-500">{UPLOAD_HINTS[result.condition]}</p>
        ) : (
          <>
            <p className="text-sm text-slate-700">{narrative?.line}</p>
            {result.strategyUsed && (
              <div className="text-xs text-slate-500">
                {STRATEGY_LABELS[result.strategyUsed] ?? result.strategyUsed}
                {result.notUsedModelIds?.length ? ` (not used: ${result.notUsedModelIds.join(', ')})` : ''}
              </div>
            )}
            <div className="space-y-2 pt-1">
              {result.contributions.map(c => (
                <Gauge key={c.modelId} score={c.score} threshold={c.threshold}
                  label={result.contributions.length > 1 ? `${c.modality} (weight ${Math.round(c.weight * 100)}%)` : undefined} />
              ))}
            </div>
            <button type="button" onClick={() => setExpanded(e => !e)}
              className="flex items-center text-xs text-teal-700 font-medium pt-1">
              How was this decided? {expanded ? <ChevronUp className="w-3.5 h-3.5 ml-1" /> : <ChevronDown className="w-3.5 h-3.5 ml-1" />}
            </button>
            {expanded && (
              <div className="text-xs text-slate-600 space-y-2 bg-slate-50 rounded-md p-3">
                <div>
                  <span className="font-medium">Models used: </span>
                  {result.contributions.map(c => `${c.modelId} (${c.modality}, weight ${Math.round(c.weight * 100)}%)`).join('; ')}
                </div>
                {result.contributions.map(c => {
                  const expl = explainability.find(e => e.modelId === c.modelId);
                  if (!expl?.features?.length) return null;
                  return (
                    <div key={c.modelId}>
                      <span className="font-medium">{c.modelId} drivers:</span>
                      <ul className="mt-1 space-y-1">
                        {expl.features.map(f => (
                          <li key={f.name} className="flex items-center">
                            {f.direction === 'up'
                              ? <AlertTriangle className="w-3 h-3 mr-1 text-red-500" />
                              : <CheckCircle2 className="w-3 h-3 mr-1 text-teal-500" />}
                            {f.name} ({f.direction === 'up' ? 'raises risk' : 'lowers risk'})
                          </li>
                        ))}
                      </ul>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function EcgWaveform({ file }: { file: File }) {
  const [values, setValues] = useState<number[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    file.text().then(text => { if (!cancelled) setValues(parseEcgText(text)); });
    return () => { cancelled = true; };
  }, [file]);
  if (!values) return <div className="text-xs text-slate-400">Loading ECG…</div>;
  const data = values.map((v, i) => ({ i, v }));
  return (
    <div className="h-24">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <YAxis hide domain={['auto', 'auto']} />
          <Line type="monotone" dataKey="v" stroke="#0d9488" dot={false} strokeWidth={1.5} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function AnalysisResult() {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const navState = (location.state as NavState | null) || null;

  const [analysis, setAnalysis] = useState<Analysis | null>(navState?.analysis ?? null);
  const [loading, setLoading] = useState(!navState?.analysis);
  const [loadError, setLoadError] = useState<string | null>(null);
  const files = navState?.files;
  const replay = navState?.replay;

  useEffect(() => {
    if (navState?.analysis || !id) return;
    setLoading(true);
    inferenceService.getAnalysis(id)
      .then(a => { setAnalysis(a); setLoadError(null); })
      .catch(e => setLoadError(e instanceof Error ? e.message : 'Could not load this analysis.'))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const { data: health } = useBackendStatus();

  const [showRawJson, setShowRawJson] = useState(false);
  const [narrative, setNarrative] = useState<Narrative | undefined>(analysis?.narrative);
  useEffect(() => setNarrative(analysis?.narrative), [analysis]);
  const [simplifying, setSimplifying] = useState(false);
  const [simplifyNote, setSimplifyNote] = useState<string | null>(null);

  const isFake = useMemo(() => {
    if (isFakeHealth(health)) return true;
    if (!analysis) return false;
    return analysis.fusion.simulated || analysis.predictions.some(p => p.simulated);
  }, [health, analysis]);

  const handleSimplify = async () => {
    if (!analysis) return;
    setSimplifying(true);
    setSimplifyNote(null);
    try {
      const n = await inferenceService.regenerateNarrative(analysis.id, true);
      setNarrative(n);
      setSimplifyNote(n.generatedBy === 'llm' ? null : 'Showing the standard wording.');
    } catch {
      setSimplifyNote('Showing the standard wording.');
    } finally {
      setSimplifying(false);
    }
  };

  const handleCopySummary = async () => {
    if (!narrative) return;
    const text = [
      narrative.headline,
      ...narrative.conditions.map(c => c.line),
      narrative.notAssessed,
      narrative.disclaimer
    ].filter(Boolean).join('\n\n');
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // clipboard access denied - nothing more we can do silently
    }
  };

  if (loading) return <div className="p-8 text-center text-slate-500">Loading analysis…</div>;
  if (loadError || !analysis) {
    return (
      <div className="p-8 text-center">
        <div className="text-red-600 font-medium mb-2">{loadError || 'Analysis not found.'}</div>
        <Button variant="outline" onClick={() => navigate('/analysis/new')}>Start a new analysis</Button>
      </div>
    );
  }

  const priority = PRIORITY_DISPLAY[narrative?.priority || 'incomplete'];
  const PriorityIcon = priority.icon;
  const llmEnabled = health?.llmEnabled ?? false;

  return (
    <div className="max-w-5xl mx-auto space-y-6 print:max-w-full">
      {isFake && (
        <div className="bg-red-600 text-white text-center py-2 rounded-md font-semibold text-sm">
          TEST MODELS — results are meaningless
        </div>
      )}
      {replay && (
        <div className="bg-amber-100 border border-amber-300 text-amber-800 text-center py-2 rounded-md text-sm font-medium">
          REPLAY — recorded {new Date(replay.recordedAt).toLocaleString()}; backend offline
        </div>
      )}

      {/* Verdict banner */}
      <Card className={`border-2 ${priority.color === 'text-red-700' ? 'border-red-200' : priority.color === 'text-teal-700' ? 'border-teal-200' : 'border-slate-200'}`}>
        <CardContent className="p-6 space-y-3">
          <div className={`flex items-center text-sm font-semibold ${priority.color}`}>
            <PriorityIcon className="w-4 h-4 mr-1.5" /> {priority.word}
          </div>
          <div className="text-xl md:text-2xl font-bold text-slate-900">{narrative?.headline}</div>
          <p className="text-sm text-slate-500">{narrative?.disclaimer}</p>
          <div className="flex items-center justify-between pt-2">
            <div className="text-xs text-slate-400">
              Wording: {narrative?.generatedBy === 'llm' ? 'AI-simplified (numbers unchanged)' : 'standard template'}
              {simplifyNote && ` — ${simplifyNote}`}
            </div>
            <div className="flex space-x-2 print:hidden">
              <Button variant="outline" size="sm" onClick={handleCopySummary}>
                <Copy className="w-3.5 h-3.5 mr-1.5" /> Copy summary
              </Button>
              <Button variant="outline" size="sm" onClick={() => window.print()}>
                <Printer className="w-3.5 h-3.5 mr-1.5" /> Print
              </Button>
              <Button
                variant="outline" size="sm" onClick={handleSimplify}
                disabled={simplifying || !llmEnabled}
                title={!llmEnabled ? 'AI wording not enabled' : undefined}
              >
                <Sparkles className="w-3.5 h-3.5 mr-1.5" /> {simplifying ? 'Simplifying…' : 'Simplify wording (AI)'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Condition cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {CONDITION_ORDER.map(condition => {
          const result = analysis.fusion.perCondition.find(c => c.condition === condition);
          if (!result) return null;
          const narrativeLine = narrative?.conditions.find(c => c.condition === condition);
          return <ConditionCard key={condition} result={result} narrative={narrativeLine} explainability={analysis.explainability} />;
        })}
      </div>

      {/* What was entered */}
      <Card>
        <CardHeader>
          <CardTitle>What Was Entered</CardTitle>
          {!files && <CardDescription>Inputs not stored — file previews are only available for the session that ran the analysis.</CardDescription>}
        </CardHeader>
        <CardContent className="space-y-4">
          {files && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {(['chestXray', 'smearCell', 'smearField'] as const).map(key => {
                const file = files[key];
                if (!file) return null;
                const url = URL.createObjectURL(file);
                return (
                  <div key={key} className="space-y-1">
                    <img src={url} alt={key} className="h-28 w-28 object-cover rounded-md border border-slate-200" />
                    <div className="text-xs text-slate-500 capitalize">{key.replace(/([A-Z])/g, ' $1')}</div>
                  </div>
                );
              })}
              {files.ecg && (
                <div className="col-span-2 md:col-span-4">
                  <div className="text-xs text-slate-500 mb-1">ECG waveform</div>
                  <EcgWaveform file={files.ecg} />
                </div>
              )}
            </div>
          )}

          {analysis.submittedValues.clinical && (
            <div>
              <div className="text-xs font-medium text-slate-600 mb-1">Clinical summary</div>
              <div className="text-sm text-slate-700 flex flex-wrap gap-x-4 gap-y-1">
                {Object.entries(analysis.submittedValues.clinical).map(([k, v]) => (
                  <span key={k}><span className="text-slate-400">{k}:</span> {String(v)}</span>
                ))}
              </div>
            </div>
          )}

          {analysis.submittedValues.lab && (
            <LabReportCard values={{
              hba1c: (analysis.submittedValues.lab as any).hba1c,
              bloodGlucose: (analysis.submittedValues.lab as any).blood_glucose ?? (analysis.submittedValues.lab as any).bloodGlucose,
              bmi: (analysis.submittedValues.clinical as any)?.bmi
            }} />
          )}
        </CardContent>
      </Card>

      {/* Flags + uncertainty */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle>Flags</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {analysis.flags.length === 0 && <div className="text-sm text-slate-400">No flags.</div>}
            {analysis.flags.map(f => (
              <div key={f.id} className="text-sm flex items-start space-x-2">
                <Badge variant={f.severity === 'high' ? 'destructive' : f.severity === 'review_required' ? 'warning' : 'secondary'}>
                  {f.severity.replace('_', ' ')}
                </Badge>
                <span className="text-slate-600">{f.reason}</span>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Uncertainty</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div>Confidence: <span className="font-medium">{Math.round(analysis.uncertainty.confidence * 100)}%</span></div>
            <div>Reliability: <span className="font-medium capitalize">{analysis.uncertainty.reliability}</span></div>
            <div className="text-slate-500 text-xs">{analysis.uncertainty.modelStatus}</div>
            <ul className="text-xs text-slate-500 list-disc list-inside">
              {analysis.uncertainty.messages.map((m, i) => <li key={i}>{m}</li>)}
            </ul>
          </CardContent>
        </Card>
      </div>

      {/* Raw response, for debugging / transparency */}
      <Card className="print:hidden">
        <CardHeader>
          <button type="button" onClick={() => setShowRawJson(s => !s)} className="flex items-center text-sm font-medium text-slate-700">
            <Code className="w-4 h-4 mr-2" /> Raw response (JSON)
            {showRawJson ? <ChevronUp className="w-4 h-4 ml-1.5" /> : <ChevronDown className="w-4 h-4 ml-1.5" />}
          </button>
        </CardHeader>
        {showRawJson && (
          <CardContent>
            <pre className="text-xs bg-slate-900 text-slate-100 rounded-md p-4 overflow-auto max-h-96">
              {JSON.stringify(analysis, null, 2)}
            </pre>
          </CardContent>
        )}
      </Card>
    </div>
  );
}
