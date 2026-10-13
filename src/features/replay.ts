import { Analysis } from '@/types';

export interface ReplayRecord {
  recordedAt: string;
  fake: boolean;
  modelVersions: Record<string, string>;
  analysis: Analysis;
}

/** Loads a recorded replay for a demo case, or null if none exists. Never throws -
 * a missing/corrupt replay file just means "no fallback available". */
export async function loadReplay(demoCaseId: string): Promise<ReplayRecord | null> {
  try {
    const resp = await fetch(`/demo/replays/${demoCaseId}.json`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

/** Only network-level failures (backend unreachable) qualify for the replay fallback -
 * a real error from a reachable backend (422, 404, 500) must still surface normally. */
export function isNetworkError(e: unknown): boolean {
  return e instanceof Error && /offline|unreachable|failed to fetch|networkerror/i.test(e.message);
}

/** The replay fallback only ever applies to a loaded demo case that failed with a
 * network-level error - hand-typed input always shows the real error, and a demo
 * case that failed for a real reason (422/404/500) is never silently swapped out. */
export function shouldAttemptReplay(hasDemoCase: boolean, error: unknown): boolean {
  return hasDemoCase && isNetworkError(error);
}
