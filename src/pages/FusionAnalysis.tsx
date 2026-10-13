import React from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Activity, Share2 } from 'lucide-react';
import { DEMO_WEIGHTS } from '@/mock/engine/lateFusionSim';
import { Condition, ModalityType } from '@/types';

const CONDITION_LABELS: Record<Condition, string> = {
  malaria: 'Malaria',
  leukemia: 'Leukemia',
  tuberculosis: 'Tuberculosis',
  hypertension: 'Hypertension',
  diabetes: 'Diabetes'
};

const MODALITY_LABELS: Record<ModalityType, string> = {
  bloodSmearCell: 'Blood Smear (Cell)',
  bloodSmearField: 'Blood Smear (Field)',
  chestXray: 'Chest X-ray',
  ecg: 'ECG',
  clinical: 'Clin',
  lab: 'Lab'
};

const CONDITION_ORDER: Condition[] = ['malaria', 'leukemia', 'tuberculosis', 'hypertension', 'diabetes'];

function formatWeights(condition: Condition): string {
  const weights = DEMO_WEIGHTS[condition];
  return (Object.keys(weights) as ModalityType[])
    .filter(m => weights[m] > 0)
    .map(m => `${MODALITY_LABELS[m]} ${Math.round(weights[m] * 100)}%`)
    .join(', ');
}

export default function FusionAnalysis() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Late Fusion Architecture</h1>
          <p className="text-slate-500 mt-1">Independent modality models converging on patient-level predictions.</p>
        </div>
        <Badge variant="outline" className="text-sm">Global View</Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="md:col-span-3">
          <Card className="min-h-[500px]">
            <CardHeader>
              <CardTitle>Fusion Diagram</CardTitle>
            </CardHeader>
            <CardContent className="flex justify-center items-center">
              {/* Fake SVG Diagram for demonstration */}
              <svg width="600" height="400" viewBox="0 0 600 400" className="max-w-full h-auto text-slate-800">
                <defs>
                  <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#cbd5e1" />
                  </marker>
                </defs>

                {/* Modality Models (Left) */}
                <g transform="translate(50, 40)">
                  {['Blood Smear (Cell/Field)', 'Chest X-ray', 'ECG', 'Clinical', 'Lab Data'].map((m, i) => (
                    <g key={m} transform={`translate(0, ${i * 70})`}>
                      <rect width="100" height="40" rx="4" fill="#f8fafc" stroke="#94a3b8" />
                      <text x="50" y="25" textAnchor="middle" fontSize="12" fill="#334155">{m}</text>
                    </g>
                  ))}
                </g>

                {/* Conditions (Middle) */}
                <g transform="translate(250, 40)">
                  {['Malaria & Leuk.', 'Tuberculosis', 'Hypertension', 'Diabetes'].map((m, i) => (
                    <g key={m} transform={`translate(0, ${i * 80 + 10})`}>
                      <rect width="100" height="40" rx="20" fill="#f0fdfa" stroke="#14b8a6" />
                      <text x="50" y="25" textAnchor="middle" fontSize="12" fill="#0f766e">{m}</text>
                    </g>
                  ))}
                </g>

                {/* Late Fusion (Right) */}
                <g transform="translate(450, 150)">
                  <rect width="120" height="60" rx="8" fill="#0f172a" stroke="#0f172a" />
                  <text x="60" y="25" textAnchor="middle" fontSize="14" fontWeight="bold" fill="#f8fafc">Late Fusion</text>
                  <text x="60" y="45" textAnchor="middle" fontSize="10" fill="#94a3b8">Patient-Level Risk</text>
                </g>

                {/* Edges from Modality to Conditions */}
                {/* Blood Smear -> Malaria/Leukemia */}
                <path d="M 150 60 C 200 60, 200 70, 250 70" stroke="#cbd5e1" strokeWidth="2" fill="none" markerEnd="url(#arrow)" />
                {/* CXR -> TB */}
                <path d="M 150 130 C 200 130, 200 150, 250 150" stroke="#cbd5e1" strokeWidth="2" fill="none" markerEnd="url(#arrow)" />
                {/* ECG -> HTN */}
                <path d="M 150 200 C 200 200, 200 230, 250 230" stroke="#cbd5e1" strokeWidth="2" fill="none" markerEnd="url(#arrow)" />
                {/* Clinical -> HTN */}
                <path d="M 150 270 C 200 270, 200 230, 250 230" stroke="#cbd5e1" strokeWidth="2" fill="none" markerEnd="url(#arrow)" />
                {/* Clinical -> DM */}
                <path d="M 150 270 C 200 270, 200 310, 250 310" stroke="#cbd5e1" strokeWidth="2" fill="none" markerEnd="url(#arrow)" />
                {/* Lab -> DM */}
                <path d="M 150 340 C 200 340, 200 310, 250 310" stroke="#cbd5e1" strokeWidth="2" fill="none" markerEnd="url(#arrow)" />

                {/* Edges from Conditions to Fusion */}
                <path d="M 350 70 C 400 70, 400 180, 450 180" stroke="#14b8a6" strokeWidth="2" fill="none" markerEnd="url(#arrow)" />
                <path d="M 350 150 C 400 150, 400 180, 450 180" stroke="#14b8a6" strokeWidth="2" fill="none" markerEnd="url(#arrow)" />
                <path d="M 350 230 C 400 230, 400 180, 450 180" stroke="#14b8a6" strokeWidth="2" fill="none" markerEnd="url(#arrow)" />
                <path d="M 350 310 C 400 310, 400 180, 450 180" stroke="#14b8a6" strokeWidth="2" fill="none" markerEnd="url(#arrow)" />
              </svg>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Why Late Fusion?</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-slate-600 space-y-4">
              <p>Each modality's model stays independent.</p>
              <p>If a modality is missing (e.g., no ECG), the system still functions without requiring retraining of the entire network.</p>
              <p>Missing modalities simply drop out of the weighting, and the fusion score is re-normalized based on available inputs.</p>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader>
              <CardTitle>Demo Weights</CardTitle>
              <CardDescription>Not medically validated</CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-slate-600 space-y-2">
              {CONDITION_ORDER.map(condition => (
                <div key={condition} className="flex justify-between">
                  <span>{CONDITION_LABELS[condition]}</span> <span>{formatWeights(condition)}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
