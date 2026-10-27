import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { inferenceService } from '../services/inference';

export function usePatients() {
  return useQuery({
    queryKey: ['patients'],
    queryFn: () => inferenceService.listPatients(),
  });
}

export function useCreatePatient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patient: { name: string; age: number; sex: 'male' | 'female' | 'other'; mrn?: string }) =>
      inferenceService.createPatient(patient),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['patients'] })
  });
}

export function usePatient(id: string) {
  return useQuery({
    queryKey: ['patient', id],
    queryFn: () => inferenceService.getPatient(id),
    enabled: !!id,
  });
}

export function useAnalyses() {
  return useQuery({
    queryKey: ['analyses'],
    queryFn: () => inferenceService.listAnalyses(),
  });
}

export function useFlags() {
  return useQuery({
    queryKey: ['flags'],
    queryFn: () => inferenceService.listFlags(),
  });
}

export function useModels() {
  return useQuery({
    queryKey: ['models'],
    queryFn: () => inferenceService.listModels(),
  });
}
