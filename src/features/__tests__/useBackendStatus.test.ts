import { describe, it, expect } from 'vitest';
import { backendStatusLevel, isFakeHealth } from '../useBackendStatus';
import { HealthStatus, HealthModelStatus } from '@/services/inference/InferenceService';

function model(state: HealthModelStatus['state'], fake = false): HealthModelStatus {
  return { id: 'm', modality: 'lab', condition: 'diabetes', state, simulatedOrFake: fake };
}

describe('backendStatusLevel', () => {
  it('is "loading" while the query is in flight', () => {
    expect(backendStatusLevel(undefined, false, true)).toBe('loading');
  });

  it('is "offline" on error or missing data', () => {
    expect(backendStatusLevel(undefined, true, false)).toBe('offline');
    expect(backendStatusLevel(undefined, false, false)).toBe('offline');
  });

  it('is "connected" when every model loaded', () => {
    const health: HealthStatus = { status: 'ok', models: [model('loaded'), model('loaded')], versions: {}, llmEnabled: false };
    expect(backendStatusLevel(health, false, false)).toBe('connected');
  });

  it('is "degraded" when some but not all models loaded', () => {
    const health: HealthStatus = { status: 'ok', models: [model('loaded'), model('missing')], versions: {}, llmEnabled: false };
    expect(backendStatusLevel(health, false, false)).toBe('degraded');
  });

  it('is "offline" when no models loaded at all', () => {
    const health: HealthStatus = { status: 'ok', models: [model('missing'), model('missing')], versions: {}, llmEnabled: false };
    expect(backendStatusLevel(health, false, false)).toBe('offline');
  });
});

describe('isFakeHealth', () => {
  it('is false with no health data', () => {
    expect(isFakeHealth(undefined)).toBe(false);
  });

  it('is false when every model is a real (non-fake) artifact', () => {
    const health: HealthStatus = { status: 'ok', models: [model('loaded', false)], versions: {}, llmEnabled: false };
    expect(isFakeHealth(health)).toBe(false);
  });

  it('is true when any model is simulated/fake', () => {
    const health: HealthStatus = { status: 'ok', models: [model('loaded', false), model('loaded', true)], versions: {}, llmEnabled: false };
    expect(isFakeHealth(health)).toBe(true);
  });
});
