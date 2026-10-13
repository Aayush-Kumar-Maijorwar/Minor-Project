import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fetchDemoCases, loadDemoCaseFiles, DemoCase } from '../demoCases';

describe('fetchDemoCases', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('fetches and parses public/demo/demo_cases.json', async () => {
    const cases = [{ id: 'x', title: 'X', description: '', patient: { name: 'P', age: 1, sex: 'male' }, note: '' }];
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => cases }));
    const result = await fetchDemoCases();
    expect(result).toEqual(cases);
    expect(fetch).toHaveBeenCalledWith('/demo/demo_cases.json');
  });

  it('throws a clear error when the file is missing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
    await expect(fetchDemoCases()).rejects.toThrow(/demo cases/i);
  });
});

describe('loadDemoCaseFiles', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('fetches each referenced asset into a real File object with the right field', async () => {
    const demoCase: DemoCase = {
      id: 'c1', title: 'Case 1', description: '', patient: { name: 'P', age: 1, sex: 'male' }, note: '',
      files: { chestXray: '/demo/chest_xray_positive.png', ecg: '/demo/ecg_abnormal.csv' }
    };
    const blob = new Blob(['data'], { type: 'image/png' });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, blob: async () => blob }));

    const files = await loadDemoCaseFiles(demoCase);

    expect(files.chestXray).toBeInstanceOf(File);
    expect(files.chestXray?.name).toBe('chest_xray.png');
    expect(files.ecg).toBeInstanceOf(File);
    expect(files.ecg?.name).toBe('ecg.csv');
    expect(files.smearCell).toBeUndefined();
    expect(files.smearField).toBeUndefined();
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('returns an empty object when the demo case has no files', async () => {
    const demoCase: DemoCase = { id: 'c2', title: 'Case 2', description: '', patient: { name: 'P', age: 1, sex: 'male' }, note: '' };
    const files = await loadDemoCaseFiles(demoCase);
    expect(files).toEqual({});
  });
});
