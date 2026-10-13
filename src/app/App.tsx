import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './Layout';

// Placeholders for Pages
const Dashboard = React.lazy(() => import('../pages/Dashboard'));
const Login = React.lazy(() => import('../pages/Login'));
const Patients = React.lazy(() => import('../pages/Patients'));
const PatientProfile = React.lazy(() => import('../pages/PatientProfile'));
const NewAnalysis = React.lazy(() => import('../pages/NewAnalysis'));
const AnalysisResult = React.lazy(() => import('../pages/AnalysisResult'));
const FusionAnalysis = React.lazy(() => import('../pages/FusionAnalysis'));
const History = React.lazy(() => import('../pages/History'));
const Flags = React.lazy(() => import('../pages/Flags'));
const Models = React.lazy(() => import('../pages/Models'));
const About = React.lazy(() => import('../pages/About'));
const Settings = React.lazy(() => import('../pages/Settings'));

const queryClient = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <React.Suspense fallback={<div className="p-8 text-center text-slate-500">Loading...</div>}>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/" element={<Dashboard />} />
              <Route path="/patients" element={<Patients />} />
              <Route path="/patients/:id" element={<PatientProfile />} />
              <Route path="/analysis/new" element={<NewAnalysis />} />
              <Route path="/analyses/:id" element={<AnalysisResult />} />
              <Route path="/fusion" element={<FusionAnalysis />} />
              <Route path="/history" element={<History />} />
              <Route path="/flags" element={<Flags />} />
              <Route path="/models" element={<Models />} />
              <Route path="/about" element={<About />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </React.Suspense>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
