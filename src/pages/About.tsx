import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';

export default function About() {
  return (
    <div className="space-y-6 max-w-4xl">
      <h1 className="text-3xl font-bold tracking-tight text-slate-900">About MedFusion</h1>
      <Card>
        <CardHeader><CardTitle>Project Overview</CardTitle></CardHeader>
        <CardContent className="space-y-4 text-slate-600">
          <p><strong>Project:</strong> MedFusion, a late-fusion multimodal AI diagnostic engine with a doctor dashboard.</p>
          <p><strong>Team:</strong> Aayush Kumar Maijorwar and Aditya Kumar Gupta</p>
          <p><strong>Guide:</strong> Shweta Kharya</p>
          <p><strong>Institute:</strong> BIT Durg, Minor Project, Phase I, CSE (AI), 5th Semester</p>
          <hr className="my-4" />
          <h3 className="font-semibold text-slate-900">The Problem</h3>
          <p>Diagnosis is fragmented, and so are the AI tools built for it. Current AI offers isolated tools, lacks multi-modal integration, and is not confidence-driven.</p>
          <h3 className="font-semibold text-slate-900">The Goal</h3>
          <p>Reliable and explainable diagnosis that supports clinical decision making, builds trust, and reduces diagnostic errors.</p>
          <h3 className="font-semibold text-slate-900">Architecture (Two Components)</h3>
          <ul className="list-disc pl-6 space-y-2">
            <li><strong>Core AI Engine:</strong> Late-fusion architecture over blood smear, chest X-ray, ECG, and lab data; screening for TB, malaria, leukemia, diabetes, and hypertension; explainability and uncertainty layers.</li>
            <li><strong>Doctor Dashboard:</strong> Patient roster, risk flags, AI report review, and treatment tracking.</li>
          </ul>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Literature & Datasets</CardTitle></CardHeader>
        <CardContent className="space-y-4 text-slate-600">
          <ul className="list-disc pl-6 space-y-2">
            <li><strong>Primary Reference:</strong> Review of deep learning-based information fusion for multimodal medical image classification (Computers in Biology and Medicine / arXiv, 2024).</li>
            <li><strong>Diabetes:</strong> iammustafatz diabetes prediction (Kaggle). Lit: Explainable ML for diabetes prediction with SHAP and LIME (Engineering Reports, 2025).</li>
            <li><strong>Hypertension:</strong> ankushpanday1 hypertension risk (Kaggle). Lit: DL digital biomarker for hypertension from ECG (npj Digital Medicine, 2025).</li>
            <li><strong>Malaria:</strong> NIH malaria cell images. Lit: DL malaria detection using red blood cell smears (Scientific Reports, 2024).</li>
            <li><strong>Leukemia:</strong> BO-ALLCNN. Lit: BO-ALLCNN Bayesian-optimized CNN for leukemia detection (PMC, 2022).</li>
            <li><strong>Tuberculosis:</strong> Qatar University TB chest X-ray. Lit: CoAtNet-based hybrid DL for TB detection in chest X-rays (PMC, 2025).</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
