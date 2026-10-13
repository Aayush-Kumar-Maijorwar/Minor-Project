import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { usePatients, useAnalyses, useFlags, useModels } from '@/features/hooks';
import { Activity, Users, AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function Dashboard() {
  const { data: patients = [], isLoading: loadingPatients } = usePatients();
  const { data: analyses = [] } = useAnalyses();
  const { data: flags = [] } = useFlags();
  const { data: models = [] } = useModels();
  
  const navigate = useNavigate();

  const highRiskPatients = patients.filter(p => p.currentRisk === 'high' || p.currentRisk === 'review_required');
  const activeFlags = flags.filter(f => f.status === 'open');

  if (loadingPatients) {
    return <div className="p-8 text-center text-slate-500">Loading dashboard data...</div>;
  }

  return (
    <div className="space-y-6">
      {/* KPI Strip */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-6 flex items-center space-x-4">
            <div className="p-3 bg-blue-100 text-blue-600 rounded-full"><Users className="w-6 h-6" /></div>
            <div>
              <p className="text-sm font-medium text-slate-500">Total Patients</p>
              <h3 className="text-2xl font-bold">{patients.length}</h3>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6 flex items-center space-x-4">
            <div className="p-3 bg-teal-100 text-teal-600 rounded-full"><Activity className="w-6 h-6" /></div>
            <div>
              <p className="text-sm font-medium text-slate-500">Total Analyses</p>
              <h3 className="text-2xl font-bold">{analyses.length}</h3>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6 flex items-center space-x-4">
            <div className="p-3 bg-red-100 text-red-600 rounded-full"><AlertTriangle className="w-6 h-6" /></div>
            <div>
              <p className="text-sm font-medium text-slate-500">High Risk</p>
              <h3 className="text-2xl font-bold">{highRiskPatients.length}</h3>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6 flex items-center space-x-4">
            <div className="p-3 bg-amber-100 text-amber-600 rounded-full"><Clock className="w-6 h-6" /></div>
            <div>
              <p className="text-sm font-medium text-slate-500">Active Alerts</p>
              <h3 className="text-2xl font-bold">{activeFlags.length}</h3>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Needs Attention */}
        <Card className="col-span-1 md:col-span-2">
          <CardHeader>
            <CardTitle>Needs Attention</CardTitle>
          </CardHeader>
          <CardContent>
            {highRiskPatients.length === 0 ? (
              <div className="text-center py-8 text-slate-500">No patients currently require immediate attention.</div>
            ) : (
              <div className="space-y-4">
                {highRiskPatients.map(p => (
                  <div key={p.id} className="flex items-center justify-between p-4 border border-slate-200 rounded-lg bg-white shadow-sm hover:border-slate-300 transition-colors cursor-pointer" onClick={() => navigate(`/patients/${p.id}`)}>
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-slate-900">{p.name}</span>
                        <Badge variant="secondary">{p.mrn}</Badge>
                        <Badge variant="outline" className="text-xs">Synthetic</Badge>
                      </div>
                      <p className="text-sm text-slate-500 mt-1">Status: {p.currentRisk?.replace('_', ' ').toUpperCase()}</p>
                    </div>
                    <Badge variant={p.currentRisk === 'high' ? 'destructive' : 'warning'}>
                      {p.currentRisk === 'high' ? 'High Risk' : 'Review Required'}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Model Status */}
        <Card>
          <CardHeader>
            <CardTitle>System Integration Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {models.map(m => (
                <div key={m.id} className="flex flex-col space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-700">{m.name}</span>
                    {m.status === 'trained_baseline' ? <CheckCircle className="w-4 h-4 text-green-500" /> : <Clock className="w-4 h-4 text-slate-400" />}
                  </div>
                  <div className="text-xs text-slate-500">
                    {m.status === 'trained_baseline' ? 'Baseline Trained' : m.status === 'tuning' ? 'Tuning in progress' : 'Planned'}
                    {' • '} {m.integrationStatus === 'mock' ? 'Mocked' : 'Integrated'}
                  </div>
                </div>
              ))}
              <div className="pt-4 mt-2 border-t border-slate-200 text-xs text-slate-400 text-center">
                {import.meta.env.VITE_INFERENCE_MODE === 'mock'
                  ? 'All models are currently running in deterministic Demo Mode.'
                  : 'Status reflects the connected backend.'}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
