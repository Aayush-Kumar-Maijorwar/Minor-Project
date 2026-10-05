import React from 'react';
import { useFlags, usePatients } from '@/features/hooks';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { AlertTriangle, Info, ShieldAlert } from 'lucide-react';
import { inferenceService } from '@/services/inference';
import { useQueryClient } from '@tanstack/react-query';

export default function Flags() {
  const { data: flags = [], isLoading: loadingFlags } = useFlags();
  const { data: patients = [] } = usePatients();
  const queryClient = useQueryClient();

  const handleUpdate = async (id: string, status: string) => {
    await inferenceService.updateFlag(id, status);
    queryClient.invalidateQueries({ queryKey: ['flags'] });
  };

  if (loadingFlags) return <div className="p-8 text-center text-slate-500">Loading flags...</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-slate-900">Risk Flags</h1>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {flags.length === 0 && (
          <div className="p-8 text-center text-slate-500 border rounded-lg bg-slate-50">No flags generated.</div>
        )}
        {flags.map(f => {
          const patient = patients.find(p => p.id === f.patientId);
          const isResolved = f.status !== 'open';
          
          return (
            <Card key={f.id} className={isResolved ? 'opacity-70 bg-slate-50' : ''}>
              <CardContent className="p-6 flex flex-col md:flex-row md:items-center justify-between space-y-4 md:space-y-0">
                <div className="flex items-start space-x-4">
                  <div className="mt-1">
                    {f.severity === 'high' ? <ShieldAlert className="w-6 h-6 text-red-500" /> :
                     f.severity === 'review_required' ? <AlertTriangle className="w-6 h-6 text-amber-500" /> :
                     <Info className="w-6 h-6 text-blue-500" />}
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-semibold text-slate-900">{patient?.name || 'Unknown Patient'}</span>
                      <Badge variant={f.severity === 'high' ? 'destructive' : f.severity === 'review_required' ? 'warning' : 'secondary'}>
                        {f.severity.replace('_', ' ').toUpperCase()}
                      </Badge>
                      {isResolved && <Badge variant="outline">Resolved</Badge>}
                    </div>
                    <p className="text-slate-600 mt-1">{f.reason}</p>
                    <div className="text-xs text-slate-400 mt-2">
                      Generated: {new Date(f.createdAt).toLocaleString()} 
                      {isResolved && ` • Reviewed: ${new Date(f.reviewedAt!).toLocaleString()} (${f.reviewAction})`}
                    </div>
                  </div>
                </div>
                {!isResolved && (
                  <div className="flex space-x-2">
                    <Button variant="outline" size="sm" onClick={() => handleUpdate(f.id, 'dismissed')}>Dismiss</Button>
                    <Button size="sm" onClick={() => handleUpdate(f.id, 'acknowledged')}>Acknowledge</Button>
                  </div>
                )}
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  );
}
