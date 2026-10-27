import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useModels } from '@/features/hooks';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { AlertTriangle, Info } from 'lucide-react';
import { ModelMetadata, Condition } from '@/types';
import { BASE_URL } from '@/services/inference/realInferenceService';

interface TunedMetrics {
  threshold: number; sensitivity: number; specificity: number; precision: number;
  accuracy: number; f1: number; tp: number; fp: number; tn: number; fn: number;
}
interface ComparisonResult {
  model?: string; arch?: string; params_m?: number; train_seconds?: number;
  val_auc: number; test_auc: number; tuned: TunedMetrics;
}
interface ComparisonJson {
  selected: string;
  results: ComparisonResult[];
  fake?: boolean;
  target_sensitivity?: number;
}
interface FusionJson {
  components: { model_id: string; weight: number }[];
  fused_threshold: number;
  fake?: boolean;
}

function absoluteUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  return `${BASE_URL}${path}`;
}

function useJson<T>(url: string | null) {
  return useQuery<T | null>({
    queryKey: ['static-json', url],
    queryFn: async () => {
      if (!url) return null;
      const resp = await fetch(url);
      if (!resp.ok) return null;
      return resp.json();
    },
    enabled: !!url
  });
}

const GROUPS: { condition: Condition; title: string }[] = [
  { condition: 'tuberculosis', title: 'Tuberculosis (chest X-ray)' },
  { condition: 'malaria', title: 'Malaria (blood-smear cell)' },
  { condition: 'leukemia', title: 'Leukemia (blood-smear field)' },
  { condition: 'diabetes', title: 'Diabetes (lab + clinical)' },
  { condition: 'hypertension', title: 'Hypertension (clinical + ECG)' }
];

const LIMITATIONS = [
  'All models are trained on public datasets, not clinical trial data.',
  'Patient-level split only for malaria; image-level splits otherwise (same patient\'s images could appear in both train and test for TB/leukemia).',
  'The ECG model is a general cardiac-abnormality proxy, not a hypertension-specific test.',
  'The hypertension model is a tabular risk proxy based on clinical fields, not a blood-pressure measurement.',
  'None of these models have been clinically validated.'
];

function pct(x: number | undefined): string {
  return x === undefined ? '—' : `${Math.round(x * 100)}%`;
}

function ModelComparisonCard({ model }: { model: ModelMetadata }) {
  const { data: comparison, isLoading } = useJson<ComparisonJson>(absoluteUrl(model.comparisonUrl));

  if (model.integrationStatus !== 'integrated') {
    return (
      <div className="p-4 bg-slate-50 border border-slate-200 rounded-md text-sm text-slate-500 flex items-center">
        <Info className="w-4 h-4 mr-2 shrink-0" /> {model.name}: not trained yet.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="font-medium text-sm text-slate-900">{model.name}</div>
        {model.fake && (
          <Badge variant="destructive">FAKE TEST ARTIFACT</Badge>
        )}
      </div>

      {isLoading && <div className="text-xs text-slate-400">Loading comparison data…</div>}

      {comparison && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-50 text-slate-500 border-y border-slate-200">
                <tr>
                  <th className="px-3 py-2 font-medium">Candidate</th>
                  <th className="px-3 py-2 font-medium">Test AUC</th>
                  <th className="px-3 py-2 font-medium">Sensitivity @thr</th>
                  <th className="px-3 py-2 font-medium">Specificity @thr</th>
                  <th className="px-3 py-2 font-medium">False Negatives</th>
                  {comparison.results[0]?.params_m !== undefined && <th className="px-3 py-2 font-medium">Params (M)</th>}
                  <th className="px-3 py-2 font-medium">Train (s)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {comparison.results.map(r => {
                  const key = r.model || r.arch || '';
                  const isSelected = key === comparison.selected;
                  return (
                    <tr key={key} className={isSelected ? 'bg-teal-50 font-medium' : ''}>
                      <td className="px-3 py-2">{key}{isSelected && <span className="text-teal-600"> *</span>}</td>
                      <td className="px-3 py-2 font-mono">{r.test_auc.toFixed(3)}</td>
                      <td className="px-3 py-2 font-mono">{pct(r.tuned.sensitivity)}</td>
                      <td className="px-3 py-2 font-mono">{pct(r.tuned.specificity)}</td>
                      <td className="px-3 py-2 font-mono">{r.tuned.fn}</td>
                      {r.params_m !== undefined && <td className="px-3 py-2 font-mono">{r.params_m}</td>}
                      <td className="px-3 py-2 font-mono">{r.train_seconds ?? '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {(() => {
            const selected = comparison.results.find(r => (r.model || r.arch) === comparison.selected);
            if (!selected) return null;
            const target = comparison.target_sensitivity !== undefined ? Math.round(comparison.target_sensitivity * 100) : 95;
            return (
              <p className="text-xs text-slate-500">
                Selected because it had the best specificity ({pct(selected.tuned.specificity)}) while keeping sensitivity ≥ {target}% on validation data; test AUC {selected.test_auc.toFixed(3)}.
              </p>
            );
          })()}

          {model.plots && model.plots.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 pt-1">
              {model.plots.map(p => (
                <img key={p} src={`${BASE_URL}${p}`} alt="model plot" className="rounded-md border border-slate-200 w-full" />
              ))}
            </div>
          )}
        </>
      )}

      {!isLoading && !comparison && (
        <div className="text-xs text-slate-400">No comparison data published for this model yet.</div>
      )}
    </div>
  );
}

function DiabetesFusionCard({ models }: { models: ModelMetadata[] }) {
  const fusionUrl = models.find(m => m.fusionUrl)?.fusionUrl;
  const { data: fusion } = useJson<FusionJson>(absoluteUrl(fusionUrl));
  if (!fusion) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Diabetes Fusion Weights</CardTitle>
        <CardDescription>weights from validation data{fusion.fake ? ' (fake test artifact)' : ''}</CardDescription>
      </CardHeader>
      <CardContent>
        <table className="w-full text-sm text-left">
          <thead className="text-slate-500 border-b border-slate-200">
            <tr><th className="py-2 font-medium">Model</th><th className="py-2 font-medium">Weight</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {fusion.components.map(c => (
              <tr key={c.model_id}>
                <td className="py-2">{c.model_id}</td>
                <td className="py-2 font-mono">{Math.round(c.weight * 100)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="text-xs text-slate-400 mt-2">Fused threshold: {fusion.fused_threshold.toFixed(2)}</div>
      </CardContent>
    </Card>
  );
}

export default function Models() {
  const { data: models = [], isLoading } = useModels();

  if (isLoading) return <div className="p-8 text-center text-slate-500">Loading models...</div>;

  const anyFake = models.some(m => m.fake);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-slate-900">Models & Integrations</h1>
      </div>

      {anyFake && (
        <div className="bg-red-600 text-white text-center py-2 rounded-md font-semibold text-sm">
          FAKE TEST ARTIFACTS — numbers below are meaningless
        </div>
      )}

      {GROUPS.map(group => {
        const groupModels = models.filter(m => m.condition === group.condition);
        if (groupModels.length === 0) return null;
        return (
          <Card key={group.condition}>
            <CardHeader>
              <CardTitle>{group.title}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {groupModels.map(m => <ModelComparisonCard key={m.id} model={m} />)}
              {group.condition === 'diabetes' && <DiabetesFusionCard models={groupModels} />}
            </CardContent>
          </Card>
        );
      })}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center"><AlertTriangle className="w-4 h-4 mr-2 text-amber-500" /> Limitations</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="list-disc list-inside text-sm text-slate-600 space-y-1">
            {LIMITATIONS.map(l => <li key={l}>{l}</li>)}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
