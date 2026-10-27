import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { usePatient, useAnalyses, useFlags } from '@/features/hooks';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ArrowRight } from 'lucide-react';
import { ModalityType } from '@/types';

const ALL_MODALITIES: ModalityType[] = ['clinical', 'lab', 'ecg', 'bloodSmearCell', 'bloodSmearField', 'chestXray'];

export default function PatientProfile() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: patient, isLoading } = usePatient(id || '');
  const { data: analyses = [] } = useAnalyses();
  const { data: flags = [] } = useFlags();

  const [activeTab, setActiveTab] = useState('overview');

  if (isLoading) return <div className="p-8 text-center text-slate-500">Loading patient...</div>;
  if (!patient) return <div className="p-8 text-center text-red-500">Patient not found</div>;

  const patientAnalyses = analyses.filter(a => a.patientId === id).sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  const latestAnalysis = patientAnalyses[0];
  const patientFlags = flags.filter(f => f.patientId === id);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center space-y-4 md:space-y-0">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold text-slate-900">{patient.name}</h1>
            <Badge variant="outline">Synthetic</Badge>
            <Badge variant={
              patient.currentRisk === 'high' ? 'destructive' :
              patient.currentRisk === 'review_required' ? 'warning' :
              patient.currentRisk === 'incomplete_data' ? 'outline' : 'secondary'
            }>
              Risk: {patient.currentRisk?.replace('_', ' ').toUpperCase()}
            </Badge>
          </div>
          <p className="text-slate-500 mt-1">{patient.mrn} • {patient.age}y • {patient.sex} • {patient.availableModalities.length}/{ALL_MODALITIES.length} Modalities Available</p>
        </div>
        <div className="flex space-x-3">
          <Button onClick={() => navigate('/analysis/new')}>Run new analysis</Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger active={activeTab === 'overview'} onClick={() => setActiveTab('overview')}>Overview</TabsTrigger>
          <TabsTrigger active={activeTab === 'analysis'} onClick={() => setActiveTab('analysis')}>Analysis</TabsTrigger>
          <TabsTrigger active={activeTab === 'history'} onClick={() => setActiveTab('history')}>History</TabsTrigger>
          <TabsTrigger active={activeTab === 'flags'} onClick={() => setActiveTab('flags')}>Flags</TabsTrigger>
        </TabsList>

        <TabsContent active={activeTab === 'overview'}>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card className="md:col-span-2">
              <CardHeader>
                <CardTitle>Current Risk Assessment</CardTitle>
                <CardDescription>
                  Based on latest late-fusion analysis
                  {latestAnalysis && ` — ${latestAnalysis.fusion.assessedConditions.length} of 5 conditions assessed`}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {latestAnalysis ? (
                  <div className="space-y-4">
                    {latestAnalysis.fusion.perCondition.map(c => (
                      <div key={c.condition} className="flex items-center justify-between p-3 border rounded-md">
                        <span className="capitalize font-medium">{c.condition}</span>
                        {c.riskLevel === 'not_assessed' ? (
                          <span className="text-slate-400 text-sm">Not assessed (input unavailable)</span>
                        ) : (
                          <div className="flex items-center space-x-4">
                            <span className="text-sm font-mono bg-slate-100 px-2 py-1 rounded">Score: {c.fusedScore.toFixed(2)}</span>
                            <Badge variant={c.riskLevel === 'high' ? 'destructive' : c.riskLevel === 'moderate' ? 'warning' : 'success'}>
                              {c.riskLevel.toUpperCase()}
                            </Badge>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-slate-500">No analysis run yet.</div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Modality Availability</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3">
                  {ALL_MODALITIES.map(mod => {
                    const isAvail = patient.availableModalities.includes(mod);
                    return (
                      <li key={mod} className="flex items-center justify-between text-sm">
                        <span className="capitalize">{mod.replace(/([A-Z])/g, ' $1').trim()}</span>
                        {isAvail ? <Badge variant="success">Available</Badge> : <Badge variant="outline">Missing</Badge>}
                      </li>
                    );
                  })}
                </ul>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent active={activeTab === 'analysis'}>
          <Card>
            <CardHeader><CardTitle>Latest Analysis</CardTitle></CardHeader>
            <CardContent>
              {latestAnalysis ? (
                <div className="space-y-4">
                  <div>
                    <div className="text-lg font-semibold text-slate-900">{latestAnalysis.narrative?.headline}</div>
                    <div className="text-sm text-slate-500 mt-1">{latestAnalysis.narrative?.disclaimer}</div>
                  </div>
                  <Button onClick={() => navigate(`/analyses/${latestAnalysis.id}`)}>
                    Open full result <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                </div>
              ) : (
                <div className="text-center py-8 text-slate-500">No analysis run yet.</div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent active={activeTab === 'history'}>
          <Card>
            <CardHeader><CardTitle>Analysis History</CardTitle></CardHeader>
            <CardContent className="p-0">
              {patientAnalyses.length === 0 ? (
                <div className="text-center py-8 text-slate-500">No analyses yet.</div>
              ) : (
                <table className="w-full text-sm text-left">
                  <thead className="bg-slate-50 text-slate-500 border-y border-slate-200">
                    <tr>
                      <th className="px-6 py-3 font-medium">Date</th>
                      <th className="px-6 py-3 font-medium">Overall Risk</th>
                      <th className="px-6 py-3 font-medium">Conditions Assessed</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {patientAnalyses.map(a => (
                      <tr key={a.id} onClick={() => navigate(`/analyses/${a.id}`)} className="hover:bg-slate-50 cursor-pointer">
                        <td className="px-6 py-4">{new Date(a.createdAt).toLocaleString()}</td>
                        <td className="px-6 py-4">
                          <Badge variant={a.fusion.overallRisk === 'high' || a.fusion.overallRisk === 'review_required' ? 'destructive' : a.fusion.overallRisk === 'moderate' ? 'warning' : a.fusion.overallRisk === 'incomplete_data' ? 'outline' : 'success'}>
                            {a.fusion.overallRisk.replace('_', ' ').toUpperCase()}
                          </Badge>
                        </td>
                        <td className="px-6 py-4">{a.fusion.assessedConditions.length} of 5</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent active={activeTab === 'flags'}>
          <Card>
            <CardHeader><CardTitle>Risk Flags</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {patientFlags.length === 0 ? (
                <div className="text-center py-8 text-slate-500">No flags for this patient.</div>
              ) : (
                patientFlags.map(f => (
                  <div key={f.id} className="flex items-start space-x-3 p-3 border border-slate-100 rounded-md">
                    <Badge variant={f.severity === 'high' ? 'destructive' : f.severity === 'review_required' ? 'warning' : 'secondary'}>
                      {f.severity.replace('_', ' ')}
                    </Badge>
                    <div className="text-sm text-slate-600">{f.reason}</div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </div>
    </div>
  );
}
