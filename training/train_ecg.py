"""
MedFusion ECG-model trainer (single-heartbeat, cardiac-abnormality screen)

Dataset: Kaggle "ECG Heartbeat Categorization Dataset" (shayanfazeli/heartbeat). That
bundle ships two file pairs for the same 187-sample-per-row beat shape - whichever is
present is used (MIT-BIH preferred if both are):
  - mitbih_train.csv / mitbih_test.csv - MIT-BIH arrhythmia beats, last column is the
    MIT-BIH class (0 = normal, 1-4 = abnormal).
  - ptbdb_normal.csv / ptbdb_abnormal.csv - PTB diagnostic database beats, already
    split by file into normal/abnormal, last column is 0/1 accordingly.
We collapse either to binary: 0 = normal, 1 = any abnormal beat, since this model is
used only as a supporting cardiac-abnormality signal for hypertension, not a
diagnosis of its own.

Trains several small 1D architectures, compares them on a held-out test set, picks the best
by VALIDATION data, tunes the decision threshold for high sensitivity, and saves weights +
metrics + plots - same conventions as train_image.py / train_tabular.py.

Kaggle usage (GPU on, Internet on, dataset attached via "Add Data"):
    !python train_ecg.py
First run a quick check:   !python train_ecg.py --smoke
"""
import argparse, copy, glob, json, os, random, shutil, time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # why: headless (Kaggle / servers)
import matplotlib.pyplot as plt
from sklearn.metrics import roc_auc_score, roc_curve, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

INPUT_LEN = 187

# ---------------------------------------------------------------------------
# Data discovery + splitting
# ---------------------------------------------------------------------------
# (filename_a, filename_b): both files share the same INPUT_LEN-samples-plus-label row shape,
# so whichever pair is found is simply concatenated. MIT-BIH preferred when both are present.
CSV_FILE_PAIRS = [("mitbih_train.csv", "mitbih_test.csv"), ("ptbdb_normal.csv", "ptbdb_abnormal.csv")]

def find_csvs(root=None) -> list[str]:
    if root:
        for a, b in CSV_FILE_PAIRS:
            pa, pb = os.path.join(root, a), os.path.join(root, b)
            if os.path.exists(pa) and os.path.exists(pb):
                return [pa, pb]
        names = " or ".join(f"{a}/{b}" for a, b in CSV_FILE_PAIRS)
        raise SystemExit(f"Neither {names} found under {root}")
    for a, b in CSV_FILE_PAIRS:
        hits = glob.glob(f"/kaggle/input/**/{a}", recursive=True)
        if hits:
            pa = hits[0]
            pb = os.path.join(os.path.dirname(pa), b)
            if os.path.exists(pb):
                return [pa, pb]
    names = " or ".join(f"{a}/{b}" for a, b in CSV_FILE_PAIRS)
    raise SystemExit(f"Neither {names} found under /kaggle/input. Attach the dataset or pass --root.")

def load_beats(csv_paths: list[str]):
    """Each row: INPUT_LEN signal samples + a trailing class column. Binarize: 0=normal, else abnormal."""
    df = pd.concat([pd.read_csv(p, header=None) for p in csv_paths], ignore_index=True)
    x = df.iloc[:, :INPUT_LEN].to_numpy(dtype=np.float32)
    y = (df.iloc[:, INPUT_LEN].to_numpy(dtype=np.int64) != 0).astype(np.float32)
    return x, y

def subsample(x, y, max_per_class, seed):
    if not max_per_class:
        return x, y
    rng = np.random.default_rng(seed)
    idx = []
    for cls in (0.0, 1.0):
        cls_idx = np.where(y == cls)[0]
        idx.append(rng.choice(cls_idx, size=min(len(cls_idx), max_per_class), replace=False))
    idx = np.concatenate(idx)
    return x[idx], y[idx]

def split_data(x, y, seed=42):
    """70/15/15, stratified (no patient ids available in the public MIT-BIH beat export)."""
    x_tr, x_tmp, y_tr, y_tmp = train_test_split(x, y, test_size=0.30, stratify=y, random_state=seed)
    x_va, x_te, y_va, y_te = train_test_split(x_tmp, y_tmp, test_size=0.50, stratify=y_tmp, random_state=seed)
    return (x_tr, y_tr), (x_va, y_va), (x_te, y_te)

# ---------------------------------------------------------------------------
# Metrics + threshold tuning (same logic as train_image.py / train_tabular.py)
# ---------------------------------------------------------------------------
def tune_threshold(y, p, target_sens=0.95):
    fpr, tpr, thr = roc_curve(y, p)
    i = int(np.argmax(tpr >= target_sens))
    t = float(thr[i])
    return 1.0 if np.isinf(t) else t

def metrics_at(y, p, thr):
    y, pred = np.asarray(y), (np.asarray(p) >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    div = lambda a, b: float(a / b) if b else 0.0
    return dict(threshold=float(thr), sensitivity=div(tp, tp + fn), specificity=div(tn, tn + fp),
                precision=div(tp, tp + fp), npv=div(tn, tn + fn), accuracy=div(tp + tn, len(y)),
                f1=float(f1_score(y, pred, zero_division=0)), tp=int(tp), fp=int(fp), tn=int(tn), fn=int(fn))

# ---------------------------------------------------------------------------
# Torch bits - these three model classes are copied verbatim into
# backend/app/predictors/ecg.py so a saved state_dict loads unchanged.
# ---------------------------------------------------------------------------
class Cnn1dSmall(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(1, 16, 7, padding=3), nn.BatchNorm1d(16), nn.ReLU(), nn.MaxPool1d(2),
            nn.Conv1d(16, 32, 5, padding=2), nn.BatchNorm1d(32), nn.ReLU(), nn.MaxPool1d(2),
            nn.Conv1d(32, 64, 3, padding=1), nn.BatchNorm1d(64), nn.ReLU(), nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Linear(64, 1)

    def forward(self, x):
        return self.head(self.net(x).squeeze(-1))

class ResidualBlock1d(nn.Module):
    def __init__(self, ch):
        super().__init__()
        self.conv1 = nn.Conv1d(ch, ch, 3, padding=1)
        self.bn1 = nn.BatchNorm1d(ch)
        self.conv2 = nn.Conv1d(ch, ch, 3, padding=1)
        self.bn2 = nn.BatchNorm1d(ch)
        self.relu = nn.ReLU()

    def forward(self, x):
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        return self.relu(out + x)

class Cnn1dResidual(nn.Module):
    def __init__(self):
        super().__init__()
        self.stem = nn.Sequential(nn.Conv1d(1, 32, 7, padding=3), nn.BatchNorm1d(32), nn.ReLU())
        self.blocks = nn.Sequential(ResidualBlock1d(32), nn.MaxPool1d(2),
                                     ResidualBlock1d(32), nn.MaxPool1d(2))
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.head = nn.Linear(32, 1)

    def forward(self, x):
        x = self.stem(x)
        x = self.blocks(x)
        x = self.pool(x).squeeze(-1)
        return self.head(x)

class BiGru(nn.Module):
    def __init__(self, hidden=32):
        super().__init__()
        self.gru = nn.GRU(input_size=1, hidden_size=hidden, num_layers=1,
                           batch_first=True, bidirectional=True)
        self.head = nn.Linear(hidden * 2, 1)

    def forward(self, x):
        # x: [B, 1, L] -> [B, L, 1]
        x = x.transpose(1, 2)
        _, h = self.gru(x)
        h = torch.cat([h[0], h[1]], dim=-1)
        return self.head(h)

ARCHS = {"cnn1d_small": Cnn1dSmall, "cnn1d_residual": Cnn1dResidual, "bigru": BiGru}

class BeatDS(Dataset):
    def __init__(self, x, y):
        self.x, self.y = x, y

    def __len__(self):
        return len(self.x)

    def __getitem__(self, i):
        return torch.tensor(self.x[i], dtype=torch.float32).unsqueeze(0), torch.tensor(self.y[i], dtype=torch.float32)

@torch.no_grad()
def predict_probs(model, loader, device):
    model.eval()
    ps, ys = [], []
    for x, y in loader:
        x = x.to(device, non_blocking=True)
        logit = model(x).squeeze(1)
        ps.append(torch.sigmoid(logit).cpu().numpy())
        ys.append(y.numpy())
    return np.concatenate(ys), np.concatenate(ps)

def train_one(arch, dl_tr, dl_va, pos_weight, epochs, lr, device):
    model = ARCHS[arch]().to(device)
    crit = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pos_weight], device=device))
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, epochs))
    best_auc, best_state, t0 = -1.0, None, time.time()
    for ep in range(epochs):
        model.train()
        run = 0.0
        for x, y in dl_tr:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            opt.zero_grad(set_to_none=True)
            loss = crit(model(x).squeeze(1), y)
            loss.backward()
            opt.step()
            run += loss.item() * len(x)
        sched.step()
        yv, pv = predict_probs(model, dl_va, device)
        auc = roc_auc_score(yv, pv)
        print(f"  [{arch}] epoch {ep+1}/{epochs}  loss={run/len(dl_tr.dataset):.4f}  val_auc={auc:.4f}")
        if auc > best_auc:  # why: keep the best epoch by VALIDATION auc, never by test
            best_auc, best_state = auc, copy.deepcopy(model.state_dict())
    model.load_state_dict(best_state)
    return model, time.time() - t0

# ---------------------------------------------------------------------------
# Plots (same style as train_image.py)
# ---------------------------------------------------------------------------
def plot_roc(results, curves, path):
    plt.figure(figsize=(6, 5))
    for r in results:
        y, p = curves[r["arch"]]
        fpr, tpr, _ = roc_curve(y, p)
        plt.plot(fpr, tpr, label=f'{r["arch"]} (AUC {r["test_auc"]:.3f})')
    plt.plot([0, 1], [0, 1], "k--", lw=0.8)
    plt.xlabel("False positive rate"); plt.ylabel("True positive rate (sensitivity)")
    plt.title("Test-set ROC"); plt.legend(loc="lower right"); plt.tight_layout()
    plt.savefig(path, dpi=150); plt.close()

def plot_comparison(results, best, path, target):
    names = [r["arch"] for r in results]
    x = np.arange(len(names)); w = 0.27
    plt.figure(figsize=(8, 4.5))
    plt.bar(x - w, [r["test_auc"] for r in results], w, label="AUC")
    plt.bar(x, [r["tuned"]["sensitivity"] for r in results], w, label="Sensitivity @thr")
    plt.bar(x + w, [r["tuned"]["specificity"] for r in results], w, label="Specificity @thr")
    plt.xticks(x, [n + (" *" if n == best else "") for n in names], rotation=15)
    plt.ylim(0, 1.05); plt.title(f"Candidate comparison (threshold tuned for sens>={target:.0%} on val)  * = selected")
    plt.legend(loc="lower right"); plt.tight_layout(); plt.savefig(path, dpi=150); plt.close()

def plot_cm(m, path, title):
    cm = np.array([[m["tn"], m["fp"]], [m["fn"], m["tp"]]])
    plt.figure(figsize=(4, 4)); plt.imshow(cm, cmap="Blues")
    for (i, j), v in np.ndenumerate(cm):
        plt.text(j, i, int(v), ha="center", va="center", fontsize=14)
    plt.xticks([0, 1], ["Pred neg", "Pred pos"]); plt.yticks([0, 1], ["True neg", "True pos"])
    plt.title(title); plt.tight_layout(); plt.savefig(path, dpi=150); plt.close()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="folder with mitbih_train.csv / mitbih_test.csv (auto-detected on Kaggle)")
    ap.add_argument("--out", default="/kaggle/working/medfusion/ecg" if os.path.exists("/kaggle") else "./medfusion_out/ecg")
    ap.add_argument("--archs", nargs="+", default=list(ARCHS), choices=list(ARCHS))
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--bs", type=int, default=256)
    ap.add_argument("--max_per_class", type=int, default=0, help="0 = use everything")
    ap.add_argument("--target_sens", type=float, default=0.95)
    ap.add_argument("--smoke", action="store_true", help="tiny run to verify the pipeline")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    if a.smoke:
        a.max_per_class, a.epochs, a.archs = 200, 1, a.archs[:2]
    random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    os.makedirs(a.out, exist_ok=True)
    print(f"Device: {device}")

    csv_paths = find_csvs(a.root)
    x, y = load_beats(csv_paths)
    x, y = subsample(x, y, a.max_per_class, a.seed)
    (x_tr, y_tr), (x_va, y_va), (x_te, y_te) = split_data(x, y, a.seed)
    print(f"Beats: {len(x)}  pos={int(y.sum())}  neg={int((1-y).sum())}")
    print(f"Split (stratified; no patient ids in the public beat export): train {len(x_tr)} / val {len(x_va)} / test {len(x_te)}")

    dl_tr = DataLoader(BeatDS(x_tr, y_tr), a.bs, shuffle=True, num_workers=0)
    dl_va = DataLoader(BeatDS(x_va, y_va), a.bs, num_workers=0)
    dl_te = DataLoader(BeatDS(x_te, y_te), a.bs, num_workers=0)
    pos = max(1, int(y_tr.sum())); pos_weight = (len(y_tr) - pos) / pos
    print(f"pos_weight = {pos_weight:.2f}")

    results, curves, states = [], {}, {}
    for arch in a.archs:
        print(f"\n=== {arch} ===")
        model, train_s = train_one(arch, dl_tr, dl_va, pos_weight, a.epochs, a.lr, device)
        yv, pv = predict_probs(model, dl_va, device)
        thr = tune_threshold(yv, pv, a.target_sens)
        t0 = time.time(); yt, pt = predict_probs(model, dl_te, device)
        infer_ms = (time.time() - t0) / len(yt) * 1000
        r = dict(arch=arch, params_m=round(sum(p.numel() for p in model.parameters()) / 1e6, 3),
                 train_seconds=round(train_s, 1), infer_ms_per_beat=round(infer_ms, 3),
                 val_auc=float(roc_auc_score(yv, pv)), test_auc=float(roc_auc_score(yt, pt)),
                 val_spec_at_target=metrics_at(yv, pv, thr)["specificity"],
                 default_0_5=metrics_at(yt, pt, 0.5), tuned=metrics_at(yt, pt, thr))
        results.append(r); curves[arch] = (yt, pt)
        states[arch] = {k: v.cpu() for k, v in model.state_dict().items()}
        t = r["tuned"]
        print(f"  TEST auc={r['test_auc']:.4f} | @thr {thr:.3f}: sens={t['sensitivity']:.3f} spec={t['specificity']:.3f} FN={t['fn']}")
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()

    best = max(results, key=lambda r: (r["val_spec_at_target"], r["val_auc"]))["arch"]
    print(f"\nSelected (by validation): {best}")

    meta = dict(task="hypertension_ecg_screen", split="stratified (no patient ids available)",
                n_train=len(x_tr), n_val=len(x_va), n_test=len(x_te),
                target_sensitivity=a.target_sens, selected=best, epochs=a.epochs, results=results,
                note="MIT-BIH public beat export; binary normal-vs-abnormal; supporting signal only, "
                     "not a hypertension-specific test; not clinical validation.")
    with open(os.path.join(a.out, "comparison.json"), "w") as f:
        json.dump(meta, f, indent=2)
    pd.DataFrame([{**{k: v for k, v in r.items() if k not in ("default_0_5", "tuned")},
                   **{f"tuned_{k}": v for k, v in r["tuned"].items()},
                   **{f"at0.5_{k}": v for k, v in r["default_0_5"].items() if k in ("sensitivity", "specificity")}}
                  for r in results]).to_csv(os.path.join(a.out, "comparison.csv"), index=False)

    b = next(r for r in results if r["arch"] == best)
    torch.save(dict(task="hypertension_ecg_screen", arch=best, state_dict=states[best], input_len=INPUT_LEN,
                    threshold=b["tuned"]["threshold"], classes=["normal", "abnormal"],
                    metrics=b["tuned"], test_auc=b["test_auc"]),
               os.path.join(a.out, "ecg_best.pt"))
    plot_roc(results, curves, os.path.join(a.out, "roc.png"))
    plot_comparison(results, best, os.path.join(a.out, "comparison.png"), a.target_sens)
    plot_cm(b["tuned"], os.path.join(a.out, "confusion_best.png"), f"{best} @ thr {b['tuned']['threshold']:.2f}")

    # A few labelled example heartbeats per class, for the Models page and the demo-data importer.
    samples_dir = os.path.join(a.out, "samples")
    os.makedirs(samples_dir, exist_ok=True)
    for cls_label, cls_name in ((0.0, "normal"), (1.0, "abnormal")):
        idx = np.where(y_te == cls_label)[0][:3]
        for i, beat_idx in enumerate(idx):
            np.savetxt(os.path.join(samples_dir, f"{cls_name}_{i}.csv"), x_te[beat_idx], delimiter=",")

    print(f"\nSaved to {a.out}: comparison.json/csv, ecg_best.pt, roc.png, comparison.png, confusion_best.png, samples/")

if __name__ == "__main__":
    main()
