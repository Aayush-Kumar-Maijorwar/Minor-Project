import { describe, it, expect } from 'vitest';
import {
  clinicalFormSchema, labFormSchema, parseEcgText, validateEcgValues,
  hasAtLeastOneInput, conditionsAssessableBy, ECG_REQUIRED_LENGTH
} from '../analysisForm';

describe('clinicalFormSchema / labFormSchema ranges', () => {
  it('accepts values inside the allowed ranges', () => {
    expect(clinicalFormSchema.safeParse({ age: 45, bmi: 25 }).success).toBe(true);
    expect(labFormSchema.safeParse({ hba1c: 6.0, bloodGlucose: 100 }).success).toBe(true);
  });

  it('rejects age outside 0-120', () => {
    expect(clinicalFormSchema.safeParse({ age: -1 }).success).toBe(false);
    expect(clinicalFormSchema.safeParse({ age: 121 }).success).toBe(false);
  });

  it('rejects bmi outside 10-70', () => {
    expect(clinicalFormSchema.safeParse({ bmi: 9 }).success).toBe(false);
    expect(clinicalFormSchema.safeParse({ bmi: 71 }).success).toBe(false);
  });

  it('rejects hba1c outside 3-15 and blood glucose outside 40-600', () => {
    expect(labFormSchema.safeParse({ hba1c: 2.9 }).success).toBe(false);
    expect(labFormSchema.safeParse({ hba1c: 15.1 }).success).toBe(false);
    expect(labFormSchema.safeParse({ bloodGlucose: 39 }).success).toBe(false);
    expect(labFormSchema.safeParse({ bloodGlucose: 601 }).success).toBe(false);
  });

  it('every field is optional - an empty object is valid', () => {
    expect(clinicalFormSchema.safeParse({}).success).toBe(true);
    expect(labFormSchema.safeParse({}).success).toBe(true);
  });
});

describe('ECG 187-value validation', () => {
  it('accepts exactly 187 comma-separated numbers', () => {
    const text = Array.from({ length: ECG_REQUIRED_LENGTH }, (_, i) => i * 0.01).join(',');
    const values = parseEcgText(text);
    expect(values.length).toBe(187);
    expect(validateEcgValues(values)).toBeNull();
  });

  it('rejects too few or too many values, naming the count', () => {
    const tooFew = parseEcgText(Array.from({ length: 100 }, () => '0.1').join(','));
    expect(validateEcgValues(tooFew)).toMatch(/187-sample heartbeat/);
    expect(validateEcgValues(tooFew)).toMatch(/100/);

    const tooMany = parseEcgText(Array.from({ length: 200 }, () => '0.1').join(','));
    expect(validateEcgValues(tooMany)).toMatch(/187-sample heartbeat/);
  });

  it('rejects non-numeric content', () => {
    const values = parseEcgText('0.1,0.2,abc,0.4');
    expect(validateEcgValues(values)).toMatch(/non-numeric/);
  });

  it('parses whitespace/semicolon/newline delimited values too', () => {
    const values = parseEcgText('0.1 0.2\n0.3;0.4');
    expect(values).toEqual([0.1, 0.2, 0.3, 0.4]);
  });
});

describe('hasAtLeastOneInput', () => {
  it('is false when nothing is filled in', () => {
    expect(hasAtLeastOneInput({})).toBe(false);
    expect(hasAtLeastOneInput({ clinical: {}, lab: {}, files: {} })).toBe(false);
  });

  it('is true when any single clinical field is set', () => {
    expect(hasAtLeastOneInput({ clinical: { age: 40 } })).toBe(true);
  });

  it('is true when any single lab field is set', () => {
    expect(hasAtLeastOneInput({ lab: { hba1c: 6 } })).toBe(true);
  });

  it('is true when a file is attached', () => {
    const file = new File(['x'], 'x.png');
    expect(hasAtLeastOneInput({ files: { chestXray: file } })).toBe(true);
  });
});

describe('conditionsAssessableBy', () => {
  it('lists Diabetes once clinical OR lab alone would assess it, not duplicated', () => {
    const result = conditionsAssessableBy({ lab: { hba1c: 7, bloodGlucose: 150 } });
    expect(result).toEqual(['Diabetes']);
  });

  it('lists both Diabetes and Hypertension once all six clinical fields are filled', () => {
    const result = conditionsAssessableBy({
      clinical: { age: 50, sex: 'Female', bmi: 25, smokingHistory: 'never', hypertension: false, heartDisease: false }
    });
    expect(result).toEqual(expect.arrayContaining(['Diabetes', 'Hypertension']));
  });

  it('lists file-driven conditions', () => {
    const file = new File(['x'], 'x.png');
    const result = conditionsAssessableBy({ files: { chestXray: file, ecg: file } });
    expect(result).toEqual(expect.arrayContaining(['Tuberculosis', 'Hypertension']));
  });
});
