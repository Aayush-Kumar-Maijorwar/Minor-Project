import { describe, it, expect, vi, afterEach } from 'vitest';
import { isNetworkError, shouldAttemptReplay, loadReplay } from '../replay';

describe('isNetworkError', () => {
  it('is true for the realInferenceService "offline or unreachable" message', () => {
    expect(isNetworkError(new Error('Backend offline or unreachable (http://localhost:8000). TypeError: Failed to fetch'))).toBe(true);
  });

  it('is false for a real HTTP error from a reachable backend', () => {
    expect(isNetworkError(new Error('age must be between 0 and 120 (got 200)'))).toBe(false);
    expect(isNetworkError(new Error('patient not found'))).toBe(false);
  });

  it('is false for a non-Error value', () => {
    expect(isNetworkError('oops')).toBe(false);
  });
});

describe('shouldAttemptReplay', () => {
  const networkErr = new Error('Backend offline or unreachable');
  const realErr = new Error('patient not found');

  it('only replays when a demo case was loaded AND the backend is unreachable', () => {
    expect(shouldAttemptReplay(true, networkErr)).toBe(true);
  });

  it('never replays hand-typed input, even on a network error', () => {
    expect(shouldAttemptReplay(false, networkErr)).toBe(false);
  });

  it('never replays a demo case that failed for a real reason (not network)', () => {
    expect(shouldAttemptReplay(true, realErr)).toBe(false);
  });
});

describe('loadReplay', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('returns the parsed record when the replay file exists', async () => {
    const record = { recordedAt: '2026-01-01T00:00:00Z', fake: true, modelVersions: {}, analysis: {} };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => record }));
    const result = await loadReplay('case-1');
    expect(result).toEqual(record);
    expect(fetch).toHaveBeenCalledWith('/demo/replays/case-1.json');
  });

  it('returns null (never throws) when no replay was recorded', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
    expect(await loadReplay('missing-case')).toBeNull();
  });

  it('returns null on a network failure too', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('boom')));
    expect(await loadReplay('case-1')).toBeNull();
  });
});
