import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export interface LabReportValues {
  hba1c?: number;
  bloodGlucose?: number;
  bmi?: number;
}

/**
 * Only these reference statements are used (Phase 3 Part E): HbA1c <5.7 normal,
 * 5.7-6.4 prediabetes range, >=6.5 diabetic range; BMI >=30 obesity range; glucose
 * shows the raw value with a footnote only - no interpretive claim beyond that.
 */
function hba1cStatus(value: number): { label: string; variant: 'success' | 'warning' | 'destructive' } {
  if (value >= 6.5) return { label: 'Diabetic range', variant: 'destructive' };
  if (value >= 5.7) return { label: 'Prediabetes range', variant: 'warning' };
  return { label: 'Normal range', variant: 'success' };
}

export function LabReportCard({ values, title = 'Lab Report' }: { values: LabReportValues; title?: string }) {
  const rows: { test: string; value: string; unit: string; range: string; status?: React.ReactNode; footnote?: string }[] = [];

  if (values.hba1c !== undefined) {
    const status = hba1cStatus(values.hba1c);
    rows.push({
      test: 'HbA1c',
      value: values.hba1c.toFixed(1),
      unit: '%',
      range: '<5.7 normal · 5.7–6.4 prediabetes · ≥6.5 diabetic',
      status: <Badge variant={status.variant}>{status.label}</Badge>
    });
  }
  if (values.bloodGlucose !== undefined) {
    rows.push({
      test: 'Blood Glucose',
      value: values.bloodGlucose.toFixed(0),
      unit: 'mg/dL',
      range: '70–99 (typical fasting)',
      footnote: 'Typical fasting range 70–99 mg/dL; sample type not recorded.'
    });
  }
  if (values.bmi !== undefined) {
    rows.push({
      test: 'BMI',
      value: values.bmi.toFixed(1),
      unit: 'kg/m²',
      range: '≥30 obesity range',
      status: values.bmi >= 30 ? <Badge variant="warning">Obesity range</Badge> : undefined
    });
  }

  if (rows.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <table className="w-full text-sm text-left">
          <thead className="bg-slate-50 text-slate-500 border-y border-slate-200">
            <tr>
              <th className="px-4 py-2 font-medium">Test</th>
              <th className="px-4 py-2 font-medium">Value</th>
              <th className="px-4 py-2 font-medium">Unit</th>
              <th className="px-4 py-2 font-medium">Typical range</th>
              <th className="px-4 py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map(r => (
              <tr key={r.test}>
                <td className="px-4 py-2 font-medium text-slate-900">{r.test}</td>
                <td className="px-4 py-2 font-mono">{r.value}</td>
                <td className="px-4 py-2 text-slate-500">{r.unit}</td>
                <td className="px-4 py-2 text-slate-500">{r.range}</td>
                <td className="px-4 py-2">{r.status || <span className="text-slate-400">—</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.some(r => r.footnote) && (
          <div className="px-4 py-2 text-xs text-slate-400 border-t border-slate-100">
            {rows.filter(r => r.footnote).map(r => <div key={r.test}>{r.footnote}</div>)}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
