import { create } from 'zustand';
import { Patient, Analysis, RiskFlag } from '@/types';

interface AppState {
  currentScenarioId: string;
  setScenarioId: (id: string) => void;
  
  demoMode: boolean;
  setDemoMode: (enabled: boolean) => void;
  
  simulateError: boolean;
  setSimulateError: (enabled: boolean) => void;
  
  // Quick cache or current selected item references
  selectedPatientId: string | null;
  setSelectedPatientId: (id: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentScenarioId: 'healthy',
  setScenarioId: (id) => set({ currentScenarioId: id }),
  
  demoMode: true,
  setDemoMode: (enabled) => set({ demoMode: enabled }),
  
  simulateError: false,
  setSimulateError: (enabled) => set({ simulateError: enabled }),
  
  selectedPatientId: null,
  setSelectedPatientId: (id) => set({ selectedPatientId: id }),
}));
