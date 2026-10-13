#!/usr/bin/env node
/**
 * Records a fresh JSON replay for every demo case by actually calling a running
 * backend, into public/demo/replays/<id>.json. The frontend's replay fallback
 * (src/features/replay.ts) uses these ONLY when the backend is unreachable AND a
 * demo case was loaded - never silently, never for hand-typed input.
 *
 * Usage (backend must be running):
 *   node scripts/record_replays.mjs [--api http://localhost:8000]
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..');
const DEMO_DIR = path.join(REPO_ROOT, 'public', 'demo');
const REPLAYS_DIR = path.join(DEMO_DIR, 'replays');

const apiArgIdx = process.argv.indexOf('--api');
const API_BASE = apiArgIdx !== -1 ? process.argv[apiArgIdx + 1] : (process.env.VITE_API_URL || 'http://localhost:8000');

async function readDemoCases() {
  const raw = await fs.readFile(path.join(DEMO_DIR, 'demo_cases.json'), 'utf8');
  return JSON.parse(raw);
}

async function fileFromDemoPath(demoPath) {
  const rel = demoPath.replace(/^\/demo\//, '');
  const filePath = path.join(DEMO_DIR, rel);
  const buf = await fs.readFile(filePath);
  const type = rel.endsWith('.png') ? 'image/png' : rel.endsWith('.csv') ? 'text/csv' : 'application/octet-stream';
  return new File([buf], path.basename(filePath), { type });
}

async function createPatient(demoCase) {
  const resp = await fetch(`${API_BASE}/patients`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: demoCase.patient.name,
      age: demoCase.patient.age,
      sex: demoCase.patient.sex,
      mrn: `DEMO-${demoCase.id}`
    })
  });
  if (!resp.ok) throw new Error(`createPatient failed: ${resp.status} ${await resp.text()}`);
  return resp.json();
}

function buildForm(demoCase, patientId, files) {
  const form = new FormData();
  form.append('patient_id', patientId);
  form.append('explain_with_llm', 'false');

  const c = demoCase.clinical;
  if (c) {
    if (c.age !== undefined) form.append('age', String(c.age));
    if (c.sex !== undefined) form.append('sex', c.sex);
    if (c.bmi !== undefined) form.append('bmi', String(c.bmi));
    if (c.smokingHistory !== undefined) form.append('smoking_history', c.smokingHistory);
    if (c.hypertension !== undefined) form.append('hypertension', String(c.hypertension));
    if (c.heartDisease !== undefined) form.append('heart_disease', String(c.heartDisease));
  }
  const l = demoCase.lab;
  if (l) {
    if (l.hba1c !== undefined) form.append('hba1c', String(l.hba1c));
    if (l.bloodGlucose !== undefined) form.append('blood_glucose', String(l.bloodGlucose));
  }
  if (files.chestXray) form.append('chest_xray', files.chestXray);
  if (files.smearCell) form.append('smear_cell', files.smearCell);
  if (files.smearField) form.append('smear_field', files.smearField);
  if (files.ecg) form.append('ecg', files.ecg);
  return form;
}

async function recordCase(demoCase, health) {
  const fake = health.models.some(m => m.simulatedOrFake);
  const modelVersions = Object.fromEntries(health.models.map(m => [m.id, m.state]));

  const patient = await createPatient(demoCase);

  const files = {};
  if (demoCase.files?.chestXray) files.chestXray = await fileFromDemoPath(demoCase.files.chestXray);
  if (demoCase.files?.smearCell) files.smearCell = await fileFromDemoPath(demoCase.files.smearCell);
  if (demoCase.files?.smearField) files.smearField = await fileFromDemoPath(demoCase.files.smearField);
  if (demoCase.files?.ecg) files.ecg = await fileFromDemoPath(demoCase.files.ecg);

  const form = buildForm(demoCase, patient.id, files);
  const resp = await fetch(`${API_BASE}/analyze`, { method: 'POST', body: form });
  if (!resp.ok) throw new Error(`/analyze failed: ${resp.status} ${await resp.text()}`);
  const analysis = await resp.json();

  const record = { recordedAt: new Date().toISOString(), fake, modelVersions, analysis };
  await fs.mkdir(REPLAYS_DIR, { recursive: true });
  await fs.writeFile(path.join(REPLAYS_DIR, `${demoCase.id}.json`), JSON.stringify(record, null, 2));
  console.log(`  recorded ${demoCase.id}.json (overallRisk=${analysis.fusion.overallRisk}${fake ? ', FAKE' : ''})`);
}

async function main() {
  console.log(`Recording replays against ${API_BASE} ...`);
  const healthResp = await fetch(`${API_BASE}/health`);
  if (!healthResp.ok) {
    console.error(`Backend not reachable at ${API_BASE} - start it first.`);
    process.exit(1);
  }
  const health = await healthResp.json();

  const demoCases = await readDemoCases();
  let failures = 0;
  for (const demoCase of demoCases) {
    try {
      await recordCase(demoCase, health);
    } catch (e) {
      failures += 1;
      console.error(`  FAILED ${demoCase.id}: ${e.message}`);
    }
  }
  console.log(failures > 0 ? `Done with ${failures} failure(s).` : 'Done.');
  if (failures > 0) process.exit(1);
}

main();
