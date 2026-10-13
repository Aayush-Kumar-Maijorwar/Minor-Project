import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { usePatient, useAnalyses } from '@/features/hooks';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Activity, AlertTriangle, FileText, Share2, History, AlertCircle } from 'lucide-react';
import { ModalityType } from '@/types';

const ALL_MODALITIES: ModalityType[] = ['clinical', 'lab', 'ecg', 'bloodSmearCell', 'bloodSmearField', 'chestXray'];

export default function PatientProfile() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: patient, isLoading } = usePatient(id || '');
  const { data: analyses = [] } = useAnalyses();
  
  const [activeTab, setActiveTab] = useState('overview');

  if (isLoading) return <div className="p-8 text-center text-slate-500">Loading patient...</div>;
  if (!patient) return <div className="p-8 text-center text-red-500">Patient not found</div>;

  const patientAnalyses = analyses.filter(a => a.patientId === id).sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  const latestAnalysis = patientAnalyses[0];

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
          <Button variant="outline" onClick={() => navigate('/analysis/new')}>Re-run with different modalities</Button>
          <Button onClick={() => navigate('/analysis/new')}>Run new analysis</Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger active={activeTab === 'overview'} onClick={() => setActiveTab('overview')}>Overview</TabsTrigger>
          <TabsTrigger active={activeTab === 'analysis'} onClick={() => setActiveTab('analysis')}>Analysis</TabsTrigger>
          <TabsTrigger active={activeTab === 'fusion'} onClick={() => setActiveTab('fusion')}>Fusion</TabsTrigger>
          <TabsTrigger active={activeTab === 'explainability'} onClick={() => setActiveTab('explainability')}>Explainability</TabsTrigger>
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
             <CardHeader><CardTitle>Analysis Detail (Simulated)</CardTitle></CardHeader>
             <CardContent>Select an analysis to view detailed modal breakdown.</CardContent>
          </Card>
        </TabsContent>
        <TabsContent active={activeTab === 'fusion'}>
          <Card>
             <CardHeader><CardTitle>Fusion Network</CardTitle></CardHeader>
             <CardContent>Interactive fusion visualization will appear here.</CardContent>
          </Card>
        </TabsContent>
        <TabsContent active={activeTab === 'explainability'}>
          <Card>
             <CardHeader><CardTitle>Explainability (Demo Mode)</CardTitle></CardHeader>
             <CardContent>Simulated SHAP/Heatmaps.</CardContent>
          </Card>
        </TabsContent>
        <TabsContent active={activeTab === 'history'}>
          <Card>
             <CardHeader><CardTitle>Timeline</CardTitle></CardHeader>
             <CardContent>Synthetic treatment tracking timeline.</CardContent>
          </Card>
        </TabsContent>
        <TabsContent active={activeTab === 'flags'}>
          <Card>
             <CardHeader><CardTitle>Risk Flags</CardTitle></CardHeader>
             <CardContent>List of active and resolved flags.</CardContent>
          </Card>
        </TabsContent>
      </div>
    </div>
  );
}
