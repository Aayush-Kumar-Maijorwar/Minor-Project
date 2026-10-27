"""
Phase 2 step 3: finds realistic tabular input values for demo cases by actually
running them through the real registered models - never guessed by hand. Searches
small grids over realistic ranges (HbA1c 4-12%, glucose 70-350 mg/dL, BMI 18-45,
age 20-85) and reports the first value set that lands in each target band:
  - clearly positive diabetes (combined model well above its threshold)
  - clearly negative diabetes (combined model well below its threshold)
  - borderline diabetes (combined model in the moderate band: >= 0.6*T and < T)
  - hypertension-positive clinical profile (hypertension_clinical above its threshold)

Usage (from backend/, venv active):
    python scripts/build_demo_cases.py
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.registry import Registry  # noqa: E402

registry = Registry(BACKEND_DIR / "artifacts", BACKEND_DIR / "config")


def diabetes_combined(hba1c, glucose, age, bmi, hypertension, heart_disease, gender, smoking_history):
    row = dict(HbA1c_level=hba1c, blood_glucose_level=glucose, age=age, bmi=bmi,
               hypertension=hypertension, heart_disease=heart_disease,
               gender=gender, smoking_history=smoking_history)
    pred = registry.run_tabular("diabetes_combined", row)
    return pred["score"], pred["threshold"]


def hypertension(age, bmi, heart_disease, gender, smoking_history):
    row = dict(age=age, bmi=bmi, heart_disease=heart_disease, gender=gender, smoking_history=smoking_history)
    pred = registry.run_tabular("hypertension_clinical", row)
    return pred["score"], pred["threshold"]


def clinical_only_diabetes(age, bmi, hypertension_flag, heart_disease, gender, smoking_history):
    row = dict(age=age, bmi=bmi, hypertension=hypertension_flag, heart_disease=heart_disease,
               gender=gender, smoking_history=smoking_history)
    pred = registry.run_tabular("diabetes_clinical", row)
    return pred["score"], pred["threshold"]


def find_clearly_positive():
    for hba1c in [9.0, 9.5, 10.0, 10.5, 11.0]:
        for glucose in [240, 260, 280, 300]:
            score, t = diabetes_combined(hba1c, glucose, 60, 32, 1, 0, "Male", "former")
            if score >= t * 1.3:
                return dict(hba1c=hba1c, glucose=glucose, age=60, bmi=32, hypertension=1,
                            heart_disease=0, gender="Male", smoking_history="former"), score, t
    raise RuntimeError("no clearly-positive grid point found")


def find_clearly_negative():
    for hba1c in [4.5, 5.0, 5.2, 5.5]:
        for glucose in [80, 90, 100, 110]:
            score, t = diabetes_combined(hba1c, glucose, 30, 22, 0, 0, "Female", "never")
            if score <= t * 0.3:
                return dict(hba1c=hba1c, glucose=glucose, age=30, bmi=22, hypertension=0,
                            heart_disease=0, gender="Female", smoking_history="never"), score, t
    raise RuntimeError("no clearly-negative grid point found")


def find_borderline():
    best = None
    for hba1c in [v / 10 for v in range(55, 75)]:
        for glucose in range(120, 200, 5):
            score, t = diabetes_combined(hba1c, glucose, 50, 29, 0, 0, "Female", "former")
            if 0.6 * t <= score < t:
                dist = abs(score - 0.8 * t)  # prefer the middle of the moderate band
                if best is None or dist < best[0]:
                    best = (dist, dict(hba1c=hba1c, glucose=glucose, age=50, bmi=29, hypertension=0,
                                        heart_disease=0, gender="Female", smoking_history="former"), score, t)
    if best is None:
        raise RuntimeError("no borderline grid point found")
    return best[1], best[2], best[3]


def find_hypertension_positive():
    for age in [65, 70, 75, 80]:
        for bmi in [32, 34, 36, 38]:
            score, t = hypertension(age, bmi, 1, "Male", "former")
            if score >= t * 1.3:
                return dict(age=age, bmi=bmi, heart_disease=1, gender="Male", smoking_history="former"), score, t
    raise RuntimeError("no hypertension-positive grid point found")


def find_clinical_only_diabetes_elevated():
    for age in [55, 60, 65]:
        for bmi in [30, 32, 34]:
            score, t = clinical_only_diabetes(age, bmi, 1, 0, "Male", "former")
            if score >= t:
                return dict(age=age, bmi=bmi, hypertension=1, heart_disease=0,
                            gender="Male", smoking_history="former"), score, t
    raise RuntimeError("no elevated clinical-only diabetes grid point found")


def main():
    print("=== clearly positive diabetes (combined) ===")
    values, score, t = find_clearly_positive()
    print(f"  {values} -> score={score:.4f} threshold={t:.4f}")

    print("=== clearly negative diabetes (combined) ===")
    values, score, t = find_clearly_negative()
    print(f"  {values} -> score={score:.4f} threshold={t:.4f}")

    print("=== borderline diabetes (combined, moderate band) ===")
    values, score, t = find_borderline()
    print(f"  {values} -> score={score:.4f} threshold={t:.4f} (band: [{0.6*t:.4f}, {t:.4f}))")

    print("=== hypertension-positive clinical profile ===")
    values, score, t = find_hypertension_positive()
    print(f"  {values} -> score={score:.4f} threshold={t:.4f}")

    print("=== clinical-only diabetes, elevated (for the clinical-only demo case) ===")
    values, score, t = find_clinical_only_diabetes_elevated()
    print(f"  {values} -> score={score:.4f} threshold={t:.4f}")


if __name__ == "__main__":
    main()
