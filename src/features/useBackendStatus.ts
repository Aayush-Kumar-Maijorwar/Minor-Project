import { useQuery } from '@tanstack/react-query';
import { inferenceService } from '@/services/inference';
import { HealthStatus } from '@/services/inference/InferenceService';

export function useBackendStatus() {
  return useQuery<HealthStatus>({
    queryKey: ['backend-health'],
    queryFn: () => inferenceService.getHealth(),
    refetchInterval: 15000,
    retry: false
  });
}

export type BackendStatusLevel = 'connected' | 'degraded' | 'offline' | 'loading';

export function backendStatusLevel(health: HealthStatus | undefined, isError: boolean, isLoading: boolean): BackendStatusLevel {
  if (isLoading) return 'loading';
  if (isError || !health) return 'offline';
  const loaded = health.models.filter(m => m.state === 'loaded').length;
  if (loaded === health.models.length) return 'connected';
  if (loaded > 0) return 'degraded';
  return 'offline';
}

export function isFakeHealth(health: HealthStatus | undefined): boolean {
  return !!health && health.models.some(m => m.simulatedOrFake);
}
