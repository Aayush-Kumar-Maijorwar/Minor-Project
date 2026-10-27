"""
Read-only verification of the user's own diabetes_best.joblib/.json (never writes to
those files). Reproduces the exact split train_diabetes.py used, re-evaluates the
joblib on that held-out test set, and checks the result against what the JSON claims.
If ANY check fails, this prints FAIL and the caller must NOT integrate the model
(train_tabular.py's retrained diabetes_combined stays the one that's used).

Usage:
    python scripts/verify_diabetes_model.py --joblib "<path>.joblib" --meta "<path>.json" --csv "<path>.csv"
"""
import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import confusion_matrix, roc_auc_score
from sklearn.model_selection import train_test_split

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = ""):
    CHECKS.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))


def reproduce_split(csv_path: Path, seed: int = 42):
    """Exactly: drop_duplicates, reset_index, then test_size=0.4 stratified split,
    then split that 40% in half (stratified) - the second half is the test set."""
    df = pd.read_csv(csv_path)
    df = df.drop_duplicates().reset_index(drop=True)
    y = df["diabetes"].astype(int)
    X_tr, X_tmp, y_tr, y_tmp = train_test_split(df, y, test_size=0.4, stratify=y, random_state=seed)
    X_va, X_te, y_va, y_te = train_test_split(X_tmp, y_tmp, test_size=0.5, stratify=y_tmp, random_state=seed)
    return X_te, y_te


def metrics_at(y, p, thr):
    y, pred = np.asarray(y), (np.asarray(p) >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    div = lambda a, b: float(a / b) if b else 0.0
    return dict(sensitivity=div(tp, tp + fn), specificity=div(tn, tn + fp), tp=int(tp), fp=int(fp), tn=int(tn), fn=int(fn))


def rel_diff(a: float, b: float) -> float:
    return abs(a - b) / b if b else abs(a - b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--joblib", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--csv", required=True)
    args = ap.parse_args()

    joblib_path, meta_path, csv_path = Path(args.joblib), Path(args.meta), Path(args.csv)
    meta = json.loads(meta_path.read_text())
    features = meta["features"]
    threshold = meta["threshold"]

    print(f"Verifying {joblib_path.name} against {meta_path.name}\n")

    # (a) reproduce the split
    X_te, y_te = reproduce_split(csv_path)
    check("reproduced the 60/20/20 split (stratified, random_state=42)", len(X_te) > 0,
          f"test set: {len(X_te)} rows, {int(y_te.sum())} positive")

    # (b) version comparison (warn, not a hard failure)
    pipe = joblib.load(joblib_path)
    installed_sklearn = sklearn.__version__
    json_sklearn = meta.get("sklearn_version")
    versions_match = installed_sklearn == json_sklearn
    if not versions_match:
        print(f"  [WARN] installed sklearn {installed_sklearn} != trained-with sklearn {json_sklearn}")
    try:
        import xgboost
        print(f"  [INFO] installed xgboost {xgboost.__version__} (not recorded in the JSON to compare against)")
    except ImportError:
        print("  [WARN] xgboost not installed - the pipeline may fail to predict")
    check("sklearn version recorded for comparison", json_sklearn is not None, f"installed={installed_sklearn} json={json_sklearn}")

    # (c) metrics on the reproduced test set vs the JSON's stored values
    try:
        proba = pipe.predict_proba(X_te[features])[:, 1]
        predict_ok = True
    except Exception as e:
        check("predict_proba runs on the reproduced test set", False, str(e))
        predict_ok = False
        proba = None

    if predict_ok:
        test_auc = roc_auc_score(y_te, proba)
        json_auc = meta["test_auc"]
        check("test AUC within 0.003 of the JSON's stored value", abs(test_auc - json_auc) <= 0.003,
              f"reproduced={test_auc:.4f} json={json_auc:.4f} diff={abs(test_auc - json_auc):.4f}")

        m = metrics_at(y_te, proba, threshold)
        json_m = meta["test_metrics"]
        check("sensitivity within 0.005 of the JSON's stored value", abs(m["sensitivity"] - json_m["sens"]) <= 0.005,
              f"reproduced={m['sensitivity']:.4f} json={json_m['sens']:.4f}")
        check("specificity within 0.005 of the JSON's stored value", abs(m["specificity"] - json_m["spec"]) <= 0.005,
              f"reproduced={m['specificity']:.4f} json={json_m['spec']:.4f}")
        check("false negatives within 2% of the JSON's stored value", rel_diff(m["fn"], json_m["FN"]) <= 0.02,
              f"reproduced={m['fn']} json={json_m['FN']}")
        check("false positives within 2% of the JSON's stored value", rel_diff(m["fp"], json_m["FP"]) <= 0.02,
              f"reproduced={m['fp']} json={json_m['FP']}")

        # (d) sanity checks
        check("predictions are in [0,1] with no NaN", bool(np.all((proba >= 0) & (proba <= 1)) and not np.any(np.isnan(proba))))

        def one_row(**overrides):
            row = {"HbA1c_level": 5.5, "blood_glucose_level": 100, "age": 45, "bmi": 27.0,
                   "hypertension": 0, "heart_disease": 0, "gender": "Female", "smoking_history": "never"}
            row.update(overrides)
            return pd.DataFrame([row])[features]

        try:
            p_other = pipe.predict_proba(one_row(gender="Other"))[:, 1][0]
            p_noinfo = pipe.predict_proba(one_row(smoking_history="No Info"))[:, 1][0]
            check("handles gender='Other' and smoking_history='No Info' without error",
                  0 <= p_other <= 1 and 0 <= p_noinfo <= 1, f"p(Other)={p_other:.4f} p(No Info)={p_noinfo:.4f}")
        except Exception as e:
            check("handles gender='Other' and smoking_history='No Info' without error", False, str(e))

        p_hba1c_5 = pipe.predict_proba(one_row(HbA1c_level=5))[:, 1][0]
        p_hba1c_10 = pipe.predict_proba(one_row(HbA1c_level=10))[:, 1][0]
        check("probability rises as HbA1c goes 5 -> 10 (other inputs typical)", p_hba1c_10 > p_hba1c_5,
              f"p(5)={p_hba1c_5:.4f} p(10)={p_hba1c_10:.4f}")

        p_glu_80 = pipe.predict_proba(one_row(blood_glucose_level=80))[:, 1][0]
        p_glu_300 = pipe.predict_proba(one_row(blood_glucose_level=300))[:, 1][0]
        check("probability rises as glucose goes 80 -> 300 (other inputs typical)", p_glu_300 > p_glu_80,
              f"p(80)={p_glu_80:.4f} p(300)={p_glu_300:.4f}")

    passed = all(ok for _, ok, _ in CHECKS)
    print(f"\n{'='*60}\nOVERALL: {'PASS' if passed else 'FAIL'} ({sum(ok for _, ok, _ in CHECKS)}/{len(CHECKS)} checks passed)\n{'='*60}")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
