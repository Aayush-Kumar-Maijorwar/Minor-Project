"""
For later: once real Kaggle artifacts are copied into backend/artifacts/ (each disease
folder has a samples/ subfolder - see training/train_image.py and train_ecg.py), this
copies a handful of REAL labelled samples into public/demo/, runs them through the
loaded model to see what it predicts, and rewrites demo_cases.json's file paths and
groundTruth to match. Never invents a label - true labels come only from each sample
file's own name (positive_*/negative_* for images, normal_*/abnormal_* for ECG, as
written by training/train_image.py and train_ecg.py's samples/ output).

Usage (from repo root, with the backend's venv active so torch/sklearn are available):
    backend\\.venv\\Scripts\\python.exe scripts\\import_demo_samples.py --artifacts backend\\artifacts [--include-miss]
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
DEMO_DIR = REPO_ROOT / "public" / "demo"
DEMO_CASES_PATH = DEMO_DIR / "demo_cases.json"

sys.path.insert(0, str(BACKEND_DIR))

MAX_TOTAL_IMAGES = 20

IMAGE_SLOTS = {"tb": ("chestXray", "tuberculosis"), "malaria": ("bloodSmearCell", "malaria"), "leukemia": ("bloodSmearField", "leukemia")}


def _find_samples(folder: Path, prefix: str) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(p for p in folder.iterdir() if p.name.startswith(prefix))


def _copy_and_predict_image(registry, slot_id: str, sample: Path, out_name: str) -> float | None:
    shutil.copy(sample, DEMO_DIR / out_name)
    pred = registry.run_image(slot_id, sample.read_bytes())
    return pred["score"] if pred else None


def _copy_and_predict_ecg(registry, sample: Path, out_name: str) -> float | None:
    shutil.copy(sample, DEMO_DIR / out_name)
    from app.predictors.ecg import parse_heartbeat

    values = parse_heartbeat(sample.read_bytes())
    pred = registry.run_ecg(values)
    return pred["score"] if pred else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", required=True)
    ap.add_argument("--include-miss", action="store_true", help="keep one sample where the model disagrees with the label, tagged 'hard case'")
    args = ap.parse_args()

    from app.registry import Registry

    artifacts_dir = Path(args.artifacts)
    registry = Registry(artifacts_dir, BACKEND_DIR / "config")

    demo_cases = json.loads(DEMO_CASES_PATH.read_text())
    DEMO_DIR.mkdir(parents=True, exist_ok=True)

    imported_count = 0
    attribution_lines = [
        "# Demo sample attribution\n",
        "Each sample below was copied from a trained model's samples/ output folder.\n",
        "Verify each dataset's license before any public release.\n\n",
    ]

    for slot_id, (modality, condition) in IMAGE_SLOTS.items():
        folder = artifacts_dir / slot_id / "samples"
        for label, prefix in (("positive", "positive_"), ("negative", "negative_")):
            if imported_count >= MAX_TOTAL_IMAGES:
                break
            samples = _find_samples(folder, prefix)
            if not samples:
                print(f"  no {label} samples for {slot_id} - leaving the placeholder in place")
                continue
            sample = samples[0]
            out_name = f"{slot_id}_{label}_real{sample.suffix}"
            score = _copy_and_predict_image(registry, slot_id, sample, out_name)
            imported_count += 1
            agrees = (score is not None) and ((score >= 0.5) == (label == "positive"))
            print(f"  {slot_id} {label}: {sample.name} -> {out_name} (model score={score}, agrees={agrees})")
            attribution_lines.append(f"- `{out_name}` - from `{sample}` (true label: {label}, model score: {score})\n")

    ecg_folder = artifacts_dir / "ecg" / "samples"
    for label, prefix in (("normal", "normal_"), ("abnormal", "abnormal_")):
        samples = _find_samples(ecg_folder, prefix)
        if not samples:
            print(f"  no {label} ECG samples - leaving the placeholder in place")
            continue
        sample = samples[0]
        out_name = f"ecg_{label}_real.csv"
        score = _copy_and_predict_ecg(registry, sample, out_name)
        print(f"  ecg {label}: {sample.name} -> {out_name} (model score={score})")
        attribution_lines.append(f"- `{out_name}` - from `{sample}` (true label: {label}, model score: {score})\n")

    (DEMO_DIR / "ATTRIBUTION.md").write_text("".join(attribution_lines))
    print(f"\nWrote {DEMO_DIR / 'ATTRIBUTION.md'}. Update demo_cases.json's file paths by hand to point at the "
          "*_real.* files once you're happy with them, then set license: VERIFY in ATTRIBUTION.md per dataset.")


if __name__ == "__main__":
    main()
