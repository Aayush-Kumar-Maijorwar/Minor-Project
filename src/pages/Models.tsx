import React from 'react';
import { useModels } from '@/features/hooks';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle, Clock } from 'lucide-react';

export default function Models() {
  const { data: models = [], isLoading } = useModels();

  if (isLoading) return <div className="p-8 text-center text-slate-500">Loading models...</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-slate-900">Models & Integrations</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {models.map(m => (
          <Card key={m.id}>
            <CardHeader>
              <div className="flex justify-between items-start">
                <CardTitle className="text-lg">{m.name}</CardTitle>
                <Badge variant={m.integrationStatus === 'mock' ? 'warning' : 'success'}>
                  {m.integrationStatus.toUpperCase()}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-y-2 text-sm">
                <div className="text-slate-500">Condition</div>
                <div className="capitalize font-medium">{m.condition}</div>
                
                <div className="text-slate-500">Input Modality</div>
                <div className="capitalize font-medium">{m.inputModality.replace(/([A-Z])/g, ' $1').trim()}</div>
                
                <div className="text-slate-500">Status</div>
                <div className="flex items-center space-x-1 font-medium">
                  {m.status === 'trained_baseline' ? <CheckCircle className="w-4 h-4 text-green-500" /> : <Clock className="w-4 h-4 text-slate-400" />}
                  <span>{m.status.replace('_', ' ').toUpperCase()}</span>
                </div>
                
                <div className="text-slate-500">Version</div>
                <div className="font-mono bg-slate-100 px-1 rounded inline-block text-xs">{m.version}</div>
                
                <div className="text-slate-500">Last Updated</div>
                <div>{m.lastUpdated}</div>
              </div>
              
              {m.integrationStatus === 'mock' && (
                <div className="pt-4 border-t border-slate-100">
                  <div className="text-sm text-amber-600 bg-amber-50 p-2 rounded flex items-start space-x-2">
                    <Clock className="w-4 h-4 mt-0.5" />
                    <span>This model is currently running in deterministic Demo Mode. Future integration will replace this mock with a live inference endpoint.</span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
