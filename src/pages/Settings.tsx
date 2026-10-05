import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { useAppStore } from '@/store/useAppStore';

export default function Settings() {
  const { demoMode, setDemoMode, simulateError, setSimulateError } = useAppStore();

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-3xl font-bold tracking-tight text-slate-900">Settings</h1>
      
      <Card>
        <CardHeader><CardTitle>Demo & Simulation Settings</CardTitle></CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-slate-900">Enable Demo Mode</p>
              <p className="text-sm text-slate-500">Run the dashboard with simulated data</p>
            </div>
            <input 
              type="checkbox" 
              checked={demoMode}
              onChange={(e) => setDemoMode(e.target.checked)}
              className="h-4 w-4 text-teal-600 rounded"
            />
          </div>
          
          <div className="flex items-center justify-between border-t border-slate-100 pt-6">
            <div>
              <p className="font-medium text-slate-900">Simulate Network Error</p>
              <p className="text-sm text-slate-500">For testing ErrorStates in UI</p>
            </div>
            <input 
              type="checkbox" 
              checked={simulateError}
              onChange={(e) => setSimulateError(e.target.checked)}
              className="h-4 w-4 text-teal-600 rounded"
            />
          </div>
        </CardContent>
      </Card>
      
      <div className="text-center text-xs text-slate-500 p-4">
        MedFusion is a research prototype intended for demonstration and academic research. Outputs are simulated in Demo Mode and are not intended for clinical diagnosis or treatment.
      </div>
    </div>
  );
}
