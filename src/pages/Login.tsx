import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Activity } from 'lucide-react';

export default function Login() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center space-y-4 pt-8">
          <div className="mx-auto w-12 h-12 bg-teal-100 rounded-full flex items-center justify-center">
            <Activity className="h-6 w-6 text-teal-600" />
          </div>
          <div className="space-y-2">
            <CardTitle className="text-2xl font-bold">
              Med<span className="text-teal-600">Fusion</span>
            </CardTitle>
            <CardDescription className="text-base">
              A late-fusion multimodal AI diagnostic engine with a doctor dashboard
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 mt-4">
          <div className="space-y-2 text-sm">
            <label className="font-medium text-slate-700">Email / Username</label>
            <input 
              type="text" 
              defaultValue="demo@medfusion.local" 
              className="w-full px-3 py-2 border border-slate-300 rounded-md bg-slate-50 text-slate-500"
              readOnly
            />
          </div>
          <div className="space-y-2 text-sm">
            <label className="font-medium text-slate-700">Password</label>
            <input 
              type="password" 
              defaultValue="password" 
              className="w-full px-3 py-2 border border-slate-300 rounded-md bg-slate-50 text-slate-500"
              readOnly
            />
          </div>
        </CardContent>
        <CardFooter className="flex-col space-y-4 pb-8">
          <Button className="w-full" size="lg" onClick={() => navigate('/')}>
            Enter Demo Mode as Dr. Demo
          </Button>
          <div className="text-center text-xs text-slate-500 max-w-[280px] mx-auto">
            MedFusion is a research prototype intended for demonstration and academic research. Outputs are simulated in Demo Mode.
            <div className="mt-2 font-medium text-slate-400">BIT Durg · Minor Project</div>
          </div>
        </CardFooter>
      </Card>
    </div>
  );
}
