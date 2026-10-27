"""
MedFusion tabular trainer  (diabetes | hypertension-risk)

Dataset: Kaggle "diabetes-prediction-dataset" (iammustafatz) - columns:
gender, age, hypertension, heart_disease, smoking_history, bmi, HbA1c_level, blood_glucose_level, diabetes

Compares Logistic Regression / Random Forest / HistGradientBoosting (+ XGBoost if installed),
selects by VALIDATION, tunes the threshold for high sensitivity, saves a ready-to-use pipeline.

Usage:   python train_tabular.py --csv path/to/diabetes_prediction_dataset.csv
(Kaggle: the CSV is auto-found under /kaggle/input)
"""
import argparse, glob, json, os, time
import numpy as np
import pandas as pd
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# why: hypertension target must not see its own label; diabetes label is also excluded
#      (a real intake form would not contain a diagnosis for another disease)
# Each task trains on the columns ONE modality would actually supply at inference time
# (backend/config/fusion.json fuses diabetes_lab + diabetes_clinical; hypertension_clinical
# is the clinical-only model for hypertension, fused with the separate ECG model).
# diabetes_combined uses every column and exists only as a reference upper bound for slides -
# it is never loaded for inference.
TASKS = {
    "diabetes_lab":          dict(target="diabetes",     cat=[],                          num=["HbA1c_level", "blood_glucose_level"]),
    "diabetes_clinical":     dict(target="diabetes",     cat=["gender", "smoking_history"], num=["age", "bmi", "hypertension", "heart_disease"]),
    "hypertension_clinical": dict(target="hypertension", cat=["gender", "smoking_history"], num=["age", "bmi", "heart_disease"]),
    "diabetes_combined":     dict(target="diabetes",     cat=["gender", "smoking_history"], num=["age", "bmi", "HbA1c_level", "blood_glucose_level", "hypertension", "heart_disease"]),
}

def find_csv(path=None):
    if path:
        return path
    hits = glob.glob("/kaggle/input/**/*.csv", recursive=True)
    hits = [h for h in hits if "diabetes" in h.lower()]
    if not hits:
        raise SystemExit("CSV not found. Attach the dataset or pass --csv.")
    return hits[0]

# --- metrics / threshold (same logic as train_image.py) ---
def tune_threshold(y, p, target_sens=0.95):
    fpr, tpr, thr = roc_curve(y, p)
    t = float(thr[int(np.argmax(tpr >= target_sens))])
    return 1.0 if np.isinf(t) else t

def metrics_at(y, p, thr):
    y, pred = np.asarray(y), (np.asarray(p) >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    div = lambda a, b: float(a / b) if b else 0.0
    return dict(threshold=float(thr), sensitivity=div(tp, tp + fn), specificity=div(tn, tn + fp),
                precision=div(tp, tp + fp), accuracy=div(tp + tn, len(y)),
                f1=float(f1_score(y, pred, zero_division=0)), tp=int(tp), fp=int(fp), tn=int(tn), fn=int(fn))

def candidates(cat_cols, num_cols, pos_weight):
    lr_steps = [("n", StandardScaler(), num_cols)]
    tree_steps = []
    if cat_cols:  # why: some tasks (e.g. diabetes_lab) are numeric-only, no categorical columns to encode
        lr_steps.insert(0, ("c", OneHotEncoder(handle_unknown="ignore"), cat_cols))
        tree_steps.append(("c", OneHotEncoder(handle_unknown="ignore"), cat_cols))
    pre_lr = ColumnTransformer(lr_steps)
    pre_tree = ColumnTransformer(tree_steps, remainder="passthrough")  # why: trees don't need scaling
    c = {
        "logistic_regression": Pipeline([("pre", pre_lr), ("m", LogisticRegression(max_iter=1000, class_weight="balanced"))]),
        "random_forest": Pipeline([("pre", pre_tree), ("m", RandomForestClassifier(
            n_estimators=300, min_samples_leaf=5, class_weight="balanced_subsample", n_jobs=-1, random_state=42))]),
        "hist_gradient_boosting": Pipeline([("pre", pre_tree), ("m", HistGradientBoostingClassifier(
            class_weight="balanced", max_iter=300, learning_rate=0.08, random_state=42))]),
    }
    try:
        from xgboost import XGBClassifier
        c["xgboost"] = Pipeline([("pre", pre_tree), ("m", XGBClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.08, scale_pos_weight=pos_weight,
            eval_metric="logloss", n_jobs=-1, random_state=42))])
    except Exception:
        pass
    return c

def run_task(name, df, out, target_sens, seed=42):
    cfg = TASKS[name]
    cols = cfg["cat"] + cfg["num"]
    X, y = df[cols], df[cfg["target"]].astype(int)
    X_tr, X_tmp, y_tr, y_tmp = train_test_split(X, y, test_size=0.30, stratify=y, random_state=seed)
    X_va, X_te, y_va, y_te = train_test_split(X_tmp, y_tmp, test_size=0.50, stratify=y_tmp, random_state=seed)
    print(f"\n##### {name}: train {len(X_tr)} / val {len(X_va)} / test {len(X_te)} | positives in train: {y_tr.mean():.1%}")
    pos_weight = (len(y_tr) - y_tr.sum()) / max(1, y_tr.sum())

    results, models, curves = [], {}, {}
    for mname, pipe in candidates(cfg["cat"], cfg["num"], pos_weight).items():
        t0 = time.time(); pipe.fit(X_tr, y_tr); train_s = time.time() - t0
        pv, pt = pipe.predict_proba(X_va)[:, 1], pipe.predict_proba(X_te)[:, 1]
        thr = tune_threshold(y_va, pv, target_sens)  # why: threshold chosen on VAL only
        r = dict(model=mname, train_seconds=round(train_s, 1),
                 val_auc=float(roc_auc_score(y_va, pv)), test_auc=float(roc_auc_score(y_te, pt)),
                 val_spec_at_target=metrics_at(y_va, pv, thr)["specificity"],
                 default_0_5=metrics_at(y_te, pt, 0.5), tuned=metrics_at(y_te, pt, thr))
        results.append(r); models[mname] = pipe; curves[mname] = pt
        t = r["tuned"]
        print(f"  {mname:24s} test AUC={r['test_auc']:.4f} | @thr {thr:.3f}: sens={t['sensitivity']:.3f} spec={t['specificity']:.3f} FN={t['fn']}")

    # why: select on validation only; test stays an honest final report
    best = max(results, key=lambda r: (r["val_spec_at_target"], r["val_auc"]))["model"]
    b = next(r for r in results if r["model"] == best)
    print(f"  -> selected (validation): {best}")

    os.makedirs(out, exist_ok=True)
    joblib.dump(models[best], os.path.join(out, f"{name}_best.joblib"))
    meta = dict(task=name, features=cols, categorical=cfg["cat"], numeric=cfg["num"], selected=best,
                threshold=b["tuned"]["threshold"], target_sensitivity=target_sens,
                n_train=len(X_tr), n_val=len(X_va), n_test=len(X_te), results=results,
                note="Held-out public-dataset split; not clinical validation.")
    with open(os.path.join(out, f"{name}_comparison.json"), "w") as f:
        json.dump(meta, f, indent=2)
    pd.DataFrame([{**{k: v for k, v in r.items() if k not in ("default_0_5", "tuned")},
                   **{f"tuned_{k}": v for k, v in r["tuned"].items()}} for r in results]
                 ).to_csv(os.path.join(out, f"{name}_comparison.csv"), index=False)

    # plots
    plt.figure(figsize=(6, 5))
    for r in results:
        fpr, tpr, _ = roc_curve(y_te, curves[r["model"]])
        plt.plot(fpr, tpr, label=f'{r["model"]} ({r["test_auc"]:.3f})')
    plt.plot([0, 1], [0, 1], "k--", lw=0.8); plt.legend(loc="lower right"); plt.title(f"{name}: test ROC")
    plt.xlabel("FPR"); plt.ylabel("Sensitivity"); plt.tight_layout()
    plt.savefig(os.path.join(out, f"{name}_roc.png"), dpi=150); plt.close()

    x = np.arange(len(results)); w = 0.27
    plt.figure(figsize=(8, 4.5))
    plt.bar(x - w, [r["test_auc"] for r in results], w, label="AUC")
    plt.bar(x, [r["tuned"]["sensitivity"] for r in results], w, label="Sensitivity @thr")
    plt.bar(x + w, [r["tuned"]["specificity"] for r in results], w, label="Specificity @thr")
    plt.xticks(x, [r["model"] + (" *" if r["model"] == best else "") for r in results], rotation=15)
    plt.ylim(0, 1.05); plt.legend(loc="lower right"); plt.title(f"{name}: candidate comparison  (* = selected)")
    plt.tight_layout(); plt.savefig(os.path.join(out, f"{name}_comparison.png"), dpi=150); plt.close()

    # feature importance for the presentation (tree models only)
    m = models[best].named_steps["m"]
    if hasattr(m, "feature_importances_"):
        names = models[best].named_steps["pre"].get_feature_names_out()
        imp = pd.Series(m.feature_importances_, index=names).sort_values()
        plt.figure(figsize=(6, 4)); imp.plot.barh(); plt.title(f"{name}: feature importance ({best})")
        plt.tight_layout(); plt.savefig(os.path.join(out, f"{name}_importance.png"), dpi=150); plt.close()

# --- late-fusion weight fitting for diabetes_lab + diabetes_clinical -----------
def norm_score(p, t):
    """Maps a model's own flag threshold t to 0.5 on a shared 0..1 scale - IDENTICAL
    formula to backend/app/fusion.py's norm_score(), so fitted weights mean the same
    thing here as they do when the backend actually fuses live predictions."""
    t = min(max(t, 1e-6), 1 - 1e-6)
    return 0.5 * p / t if p < t else 0.5 + 0.5 * (p - t) / (1 - t)

def fuse_diabetes(df, out, target_sens, seed=42):
    """Fits late-fusion weights for diabetes_lab + diabetes_clinical. Reuses the exact
    same 70/15/15 split (same df, target column, seed) run_task() used for those two
    tasks, so this reloads their already-saved joblib/comparison.json rather than
    retraining anything. Weight search + threshold tuning happen on VALIDATION only;
    test stays an honest final report. Writes out/diabetes_fusion.json in the shape
    the backend registry expects (components + fused_threshold)."""
    lab_meta = json.load(open(os.path.join(out, "diabetes_lab_comparison.json")))
    clin_meta = json.load(open(os.path.join(out, "diabetes_clinical_comparison.json")))
    lab_pipe = joblib.load(os.path.join(out, "diabetes_lab_best.joblib"))
    clin_pipe = joblib.load(os.path.join(out, "diabetes_clinical_best.joblib"))

    y = df["diabetes"].astype(int)
    X_tr, X_tmp, y_tr, y_tmp = train_test_split(df, y, test_size=0.30, stratify=y, random_state=seed)
    X_va, X_te, y_va, y_te = train_test_split(X_tmp, y_tmp, test_size=0.50, stratify=y_tmp, random_state=seed)

    p_lab_va = lab_pipe.predict_proba(X_va[lab_meta["features"]])[:, 1]
    p_clin_va = clin_pipe.predict_proba(X_va[clin_meta["features"]])[:, 1]
    p_lab_te = lab_pipe.predict_proba(X_te[lab_meta["features"]])[:, 1]
    p_clin_te = clin_pipe.predict_proba(X_te[clin_meta["features"]])[:, 1]

    t_lab, t_clin = lab_meta["threshold"], clin_meta["threshold"]
    ns_lab_va = np.array([norm_score(p, t_lab) for p in p_lab_va])
    ns_clin_va = np.array([norm_score(p, t_clin) for p in p_clin_va])
    ns_lab_te = np.array([norm_score(p, t_lab) for p in p_lab_te])
    ns_clin_te = np.array([norm_score(p, t_clin) for p in p_clin_te])

    # why: grid search over the fusion weight, same selection rule as everywhere else
    # in this codebase - best specificity at the target sensitivity, chosen on VAL only
    best = None
    for w_lab in np.linspace(0.0, 1.0, 21):
        fused_va = w_lab * ns_lab_va + (1 - w_lab) * ns_clin_va
        thr = tune_threshold(y_va, fused_va, target_sens)
        spec = metrics_at(y_va, fused_va, thr)["specificity"]
        key = (spec, roc_auc_score(y_va, fused_va))
        if best is None or key > best[0]:
            best = (key, float(w_lab), float(thr))
    _, w_lab, fused_threshold = best
    w_clin = 1 - w_lab

    fused_te = w_lab * ns_lab_te + w_clin * ns_clin_te
    test_auc = float(roc_auc_score(y_te, fused_te))
    tuned = metrics_at(y_te, fused_te, fused_threshold)

    fusion = dict(
        components=[
            dict(model_id="diabetes_lab", weight=round(w_lab, 3)),
            dict(model_id="diabetes_clinical", weight=round(w_clin, 3)),
        ],
        fused_threshold=round(fused_threshold, 4),
        test_auc=test_auc,
        tuned=tuned,
        weights_source="fitted on validation data (grid search, norm_score fusion - same mapping as backend/app/fusion.py)",
        note="Held-out public-dataset split; not clinical validation.",
    )
    with open(os.path.join(out, "diabetes_fusion.json"), "w") as f:
        json.dump(fusion, f, indent=2)
    print(f"\n##### diabetes fusion: w_lab={w_lab:.2f} w_clinical={w_clin:.2f} fused_threshold={fused_threshold:.3f}")
    print(f"  TEST fused auc={test_auc:.4f} sens={tuned['sensitivity']:.3f} spec={tuned['specificity']:.3f} FN={tuned['fn']}")
    return fusion

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=None)
    ap.add_argument("--out", default="/kaggle/working/medfusion/tabular" if os.path.exists("/kaggle") else "./medfusion_out/tabular")
    ap.add_argument("--target_sens", type=float, default=0.95)
    ap.add_argument("--tasks", "--models", nargs="+", default=list(TASKS), choices=list(TASKS), dest="tasks")
    a = ap.parse_args()
    df = pd.read_csv(find_csv(a.csv))
    n0 = len(df)
    df = df.drop_duplicates().reset_index(drop=True)  # why: exact duplicate rows would leak across splits
    print(f"Rows: {n0} -> {len(df)} after dropping exact duplicates")
    for t in a.tasks:
        run_task(t, df, a.out, a.target_sens)
    if "diabetes_lab" in a.tasks and "diabetes_clinical" in a.tasks:
        fuse_diabetes(df, a.out, a.target_sens)
    print(f"\nSaved to {a.out}")

if __name__ == "__main__":
    main()
