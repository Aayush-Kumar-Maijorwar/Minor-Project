import React from 'react';
import { useAnalyses, usePatients } from '@/features/hooks';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useNavigate } from 'react-router-dom';

export default function History() {
  const { data: analyses = [], isLoading: loadingAnalyses } = useAnalyses();
  const { data: patients = [], isLoading: loadingPatients } = usePatients();
  const navigate = useNavigate();

  if (loadingAnalyses || loadingPatients) return <div className="p-8 text-center text-slate-500">Loading history...</div>;

  const sortedAnalyses = [...analyses].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-slate-900">Prediction History</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Analyses</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 text-slate-500 border-y border-slate-200">
                <tr>
                  <th className="px-6 py-3 font-medium">Date</th>
                  <th className="px-6 py-3 font-medium">Patient</th>
                  <th className="px-6 py-3 font-medium">Overall Risk</th>
                  <th className="px-6 py-3 font-medium">Dominant Condition</th>
                  <th className="px-6 py-3 font-medium">Modalities Used</th>
                  <th className="px-6 py-3 font-medium">Version</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {sortedAnalyses.map(a => {
                  const p = patients.find(p => p.id === a.patientId);
                  return (
                    <tr 
                      key={a.id} 
                      onClick={() => navigate(`/patients/${a.patientId}`)}
                      className="hover:bg-slate-50 cursor-pointer transition-colors"
                    >
                      <td className="px-6 py-4 text-slate-600 whitespace-nowrap">
                        {new Date(a.createdAt).toLocaleString()}
                      </td>
                      <td className="px-6 py-4">
                        <div className="font-medium text-slate-900">{p?.name || 'Unknown'}</div>
                      </td>
                      <td className="px-6 py-4">
                        <Badge variant={a.fusion.overallRisk === 'high' ? 'destructive' : a.fusion.overallRisk === 'review_required' ? 'warning' : 'secondary'}>
                          {a.fusion.overallRisk.toUpperCase()}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-slate-600 capitalize">
                        {a.fusion.dominantCondition || 'N/A'}
                      </td>
                      <td className="px-6 py-4 text-slate-600">
                        {a.fusion.modalitiesUsed.length} / 6
                      </td>
                      <td className="px-6 py-4 text-slate-600">
                        {a.fusion.fusionVersion}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {sortedAnalyses.length === 0 && (
             <div className="text-center py-8 text-slate-500">No analyses found in history.</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
