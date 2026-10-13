"""
MedFusion image-model trainer  (TB X-ray | malaria cells | leukemia smear)

Trains several candidate CNNs on ONE disease, compares them on a held-out test set,
picks the best by VALIDATION data, tunes the decision threshold for high sensitivity,
and saves weights + metrics + plots for the presentation and the backend.

Kaggle usage (GPU on, Internet on, dataset attached via "Add Data"):
    !python train_image.py --disease tb
    !python train_image.py --disease malaria
    !python train_image.py --disease leukemia
First run a quick check:   !python train_image.py --disease tb --smoke
"""
import argparse, copy, glob, json, os, random, re, time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # why: headless (Kaggle / servers)
import matplotlib.pyplot as plt
from PIL import Image
from sklearn.metrics import (roc_auc_score, roc_curve, confusion_matrix, f1_score)
from sklearn.model_selection import train_test_split, GroupShuffleSplit

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms

IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
IMAGENET_MEAN, IMAGENET_STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]

# ---------------------------------------------------------------------------
# Per-disease config
# ---------------------------------------------------------------------------
# label_fn gets the PARENT FOLDER NAME and returns 1 (disease), 0 (healthy) or None (skip)
def _tb_label(folder):
    f = folder.lower()
    return 1 if f == "tuberculosis" else 0 if f == "normal" else None

def _malaria_label(folder):
    f = folder.lower()
    return 1 if f == "parasitized" else 0 if f == "uninfected" else None

def _leuk_label(folder):
    f = folder.lower()
    # why: 4-class dataset -> binary "any ALL subtype vs benign" for the verdict
    return 1 if f.startswith("[malignant]") else 0 if f == "benign" else None

def _malaria_group(path):
    # why: NIH cell files are named like C100P61ThinF_IMG_..._cell_162.png -> prefix = patient/slide.
    # Splitting by patient prevents the same patient's cells leaking into train AND test.
    name = os.path.basename(path)
    return re.split(r"thinf", name, flags=re.I)[0].strip("_")

CFG = {
    "tb":       dict(hint="tuberculosis", label_fn=_tb_label,      group_fn=None,           img=224, vflip=False, bs=32),
    "malaria":  dict(hint="malaria",      label_fn=_malaria_label, group_fn=_malaria_group, img=128, vflip=True,  bs=64),
    "leukemia": dict(hint="blood-cell",   label_fn=_leuk_label,    group_fn=None,           img=224, vflip=True,  bs=32),
}

# ---------------------------------------------------------------------------
# Data discovery + splitting
# ---------------------------------------------------------------------------
def find_root(disease, root=None):
    if root:
        return root
    hint = CFG[disease]["hint"]
    hits = [p for p in glob.glob("/kaggle/input/*") if hint in os.path.basename(p).lower()]
    if not hits:
        raise SystemExit(f"No dataset folder matching '{hint}' under /kaggle/input. Attach it or pass --root.")
    return hits[0]

def discover(disease, root):
    """Walk the dataset, label by parent-folder name, de-duplicate nested copies."""
    cfg, rows, seen = CFG[disease], [], set()
    for dirpath, _, files in os.walk(root):
        label = cfg["label_fn"](os.path.basename(dirpath))
        if label is None:
            continue
        for fn in files:
            if os.path.splitext(fn)[1].lower() not in IMG_EXT:
                continue
            # why: key on parent-folder name too - leukemia subfolders reuse file names (Snap_001.jpg),
            #      while the Kaggle malaria zip contains the same folder twice and must collapse
            key = (os.path.basename(dirpath), fn)
            if key in seen:
                continue
            seen.add(key)
            p = os.path.join(dirpath, fn)
            rows.append(dict(path=p, label=label, group=cfg["group_fn"](p) if cfg["group_fn"] else None))
    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit(f"No labelled images found under {root}")
    return df

def subsample(df, max_per_class, seed):
    if not max_per_class:
        return df
    parts = [g.sample(min(len(g), max_per_class), random_state=seed) for _, g in df.groupby("label")]
    return pd.concat(parts).reset_index(drop=True)

def split_data(df, seed=42):
    """70/15/15. Group-aware when patient ids exist, else stratified."""
    use_groups = df["group"].notna().all() and df["group"].nunique() >= 20
    if use_groups:
        g1 = GroupShuffleSplit(n_splits=1, test_size=0.30, random_state=seed)
        tr, tmp = next(g1.split(df, df["label"], df["group"]))
        d_tr, d_tmp = df.iloc[tr], df.iloc[tmp]
        g2 = GroupShuffleSplit(n_splits=1, test_size=0.50, random_state=seed)
        va, te = next(g2.split(d_tmp, d_tmp["label"], d_tmp["group"]))
        d_va, d_te = d_tmp.iloc[va], d_tmp.iloc[te]
        ok = all(d["label"].nunique() == 2 for d in (d_tr, d_va, d_te))
        if ok:
            return d_tr, d_va, d_te, "patient-level (grouped)"
        print("WARNING: grouped split lost a class in some split; falling back to stratified.")
    d_tr, d_tmp = train_test_split(df, test_size=0.30, stratify=df["label"], random_state=seed)
    d_va, d_te = train_test_split(d_tmp, test_size=0.50, stratify=d_tmp["label"], random_state=seed)
    return d_tr, d_va, d_te, "image-level (stratified; no patient ids available)"

# ---------------------------------------------------------------------------
# Metrics + threshold tuning (pure numpy/sklearn)
# ---------------------------------------------------------------------------
def tune_threshold(y, p, target_sens=0.95):
    """Highest threshold that still reaches target sensitivity (=> max specificity)."""
    fpr, tpr, thr = roc_curve(y, p)
    i = int(np.argmax(tpr >= target_sens))  # first index meeting target = lowest FPR
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
# Torch bits
# ---------------------------------------------------------------------------
class ImgDS(Dataset):
    def __init__(self, df, tf):
        self.paths, self.labels, self.tf = df["path"].tolist(), df["label"].tolist(), tf
    def __len__(self):
        return len(self.paths)
    def __getitem__(self, i):
        img = Image.open(self.paths[i]).convert("RGB")  # why: X-rays are grayscale, backbones expect 3ch
        return self.tf(img), torch.tensor(self.labels[i], dtype=torch.float32)

def make_tfms(size, vflip):
    norm = transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD)
    train = [transforms.Resize((size, size)), transforms.RandomHorizontalFlip(),
             transforms.RandomRotation(10)]
    if vflip:
        train.insert(2, transforms.RandomVerticalFlip())
    train += [transforms.ToTensor(), norm]
    evalt = [transforms.Resize((size, size)), transforms.ToTensor(), norm]
    return transforms.Compose(train), transforms.Compose(evalt)

def build_model(arch, pretrained=True):
    w = "IMAGENET1K_V1" if pretrained else None
    try:
        m = getattr(models, arch)(weights=w)
    except Exception as e:  # why: offline notebook -> still run, but say so loudly
        print(f"WARNING: could not load pretrained {arch} ({e}); using random init.")
        m = getattr(models, arch)(weights=None)
    if arch == "resnet18":
        m.fc = nn.Linear(m.fc.in_features, 1)
    elif arch == "densenet121":
        m.classifier = nn.Linear(m.classifier.in_features, 1)
    elif arch in ("efficientnet_b0", "mobilenet_v3_small"):
        m.classifier[-1] = nn.Linear(m.classifier[-1].in_features, 1)
    else:
        raise ValueError(arch)
    return m

@torch.no_grad()
def predict_probs(model, loader, device):
    model.eval()
    ps, ys = [], []
    for x, y in loader:
        x = x.to(device, non_blocking=True)
        with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
            logit = model(x).squeeze(1)
        ps.append(torch.sigmoid(logit.float()).cpu().numpy())
        ys.append(y.numpy())
    return np.concatenate(ys), np.concatenate(ps)

def train_one(arch, dl_tr, dl_va, pos_weight, epochs, lr, device, pretrained):
    model = build_model(arch, pretrained).to(device)
    # why: pos_weight>1 makes a missed positive cost more -> favours sensitivity
    crit = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pos_weight], device=device))
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, epochs))
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    best_auc, best_state, t0 = -1.0, None, time.time()
    for ep in range(epochs):
        model.train()
        run = 0.0
        for x, y in dl_tr:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                loss = crit(model(x).squeeze(1), y)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
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
# Plots
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
    plt.bar(x, [r["tuned"]["sensitivity"] for r in results], w, label=f"Sensitivity @thr")
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
    ap.add_argument("--disease", required=True, choices=list(CFG))
    ap.add_argument("--root", default=None, help="dataset folder (auto-detected on Kaggle)")
    ap.add_argument("--out", default="/kaggle/working/medfusion" if os.path.exists("/kaggle") else "./medfusion_out")
    ap.add_argument("--archs", nargs="+", default=["resnet18", "efficientnet_b0", "mobilenet_v3_small", "densenet121"])
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--bs", type=int, default=None)
    ap.add_argument("--max_per_class", type=int, default=0, help="0 = use everything")
    ap.add_argument("--target_sens", type=float, default=0.95)
    ap.add_argument("--no_pretrained", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="tiny run to verify the pipeline")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    if a.smoke:
        a.max_per_class, a.epochs, a.archs = 64, 1, a.archs[:2]
    random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)
    cfg, device = CFG[a.disease], torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out = os.path.join(a.out, a.disease); os.makedirs(out, exist_ok=True)
    print(f"Device: {device} | disease: {a.disease}")

    root = find_root(a.disease, a.root)
    df = subsample(discover(a.disease, root), a.max_per_class, a.seed)
    d_tr, d_va, d_te, split_kind = split_data(df, a.seed)
    print(f"Images: {len(df)}  pos={int(df.label.sum())}  neg={int((1-df.label).sum())}")
    print(f"Split: {split_kind} -> train {len(d_tr)} / val {len(d_va)} / test {len(d_te)}")

    tf_tr, tf_ev = make_tfms(cfg["img"], cfg["vflip"])
    bs = a.bs or cfg["bs"]
    nw = 2
    dl_tr = DataLoader(ImgDS(d_tr, tf_tr), bs, shuffle=True, num_workers=nw, pin_memory=True)
    dl_va = DataLoader(ImgDS(d_va, tf_ev), bs, num_workers=nw, pin_memory=True)
    dl_te = DataLoader(ImgDS(d_te, tf_ev), bs, num_workers=nw, pin_memory=True)
    pos = max(1, int(d_tr.label.sum())); pos_weight = (len(d_tr) - pos) / pos
    print(f"pos_weight = {pos_weight:.2f}")

    results, curves, states = [], {}, {}
    for arch in a.archs:
        print(f"\n=== {arch} ===")
        model, train_s = train_one(arch, dl_tr, dl_va, pos_weight, a.epochs, a.lr, device, not a.no_pretrained)
        yv, pv = predict_probs(model, dl_va, device)
        thr = tune_threshold(yv, pv, a.target_sens)           # why: threshold chosen on VAL only
        t0 = time.time(); yt, pt = predict_probs(model, dl_te, device)
        infer_ms = (time.time() - t0) / len(yt) * 1000
        r = dict(arch=arch, params_m=round(sum(p.numel() for p in model.parameters()) / 1e6, 2),
                 train_seconds=round(train_s, 1), infer_ms_per_img=round(infer_ms, 2),
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

    # why: model selection uses VALIDATION numbers only (test stays untouched for honest reporting)
    best = max(results, key=lambda r: (r["val_spec_at_target"], r["val_auc"]))["arch"]
    print(f"\nSelected (by validation): {best}")

    meta = dict(disease=a.disease, split=split_kind, n_train=len(d_tr), n_val=len(d_va), n_test=len(d_te),
                target_sensitivity=a.target_sens, selected=best, epochs=a.epochs, results=results,
                note="Held-out public-dataset split; not clinical validation.")
    with open(os.path.join(out, "comparison.json"), "w") as f:
        json.dump(meta, f, indent=2)
    pd.DataFrame([{**{k: v for k, v in r.items() if k not in ("default_0_5", "tuned")},
                   **{f"tuned_{k}": v for k, v in r["tuned"].items()},
                   **{f"at0.5_{k}": v for k, v in r["default_0_5"].items() if k in ("sensitivity", "specificity")}}
                  for r in results]).to_csv(os.path.join(out, "comparison.csv"), index=False)

    b = next(r for r in results if r["arch"] == best)
    torch.save(dict(disease=a.disease, arch=best, state_dict=states[best], img_size=cfg["img"],
                    threshold=b["tuned"]["threshold"], mean=IMAGENET_MEAN, std=IMAGENET_STD,
                    classes=["negative", "positive"], metrics=b["tuned"], test_auc=b["test_auc"]),
               os.path.join(out, f"{a.disease}_best.pt"))
    plot_roc(results, curves, os.path.join(out, "roc.png"))
    plot_comparison(results, best, os.path.join(out, "comparison.png"), a.target_sens)
    plot_cm(b["tuned"], os.path.join(out, "confusion_best.png"), f"{best} @ thr {b['tuned']['threshold']:.2f}")
    print(f"\nSaved to {out}: comparison.json/csv, {a.disease}_best.pt, roc.png, comparison.png, confusion_best.png")

if __name__ == "__main__":
    main()
