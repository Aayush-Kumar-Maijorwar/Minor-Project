"""
Loads every real model through the registry (same code path the API uses) and runs
ONE prediction per loaded model: a sample image from its artifacts/<disease>/samples/
folder for image models, or a fixed/reference row of tabular values for tabular
models. Prints probability, threshold, and the resulting decision (compares against
the model's OWN stored threshold - never a hardcoded 0.5).

Models that are missing, errored, or refused by the quality gate are reported as such,
never silently skipped.

Usage (from backend/, with the venv active):
    python scripts/predict_one.py [--artifacts artifacts]
"""
import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.registry import Registry  # noqa: E402

IMAGE_SAMPLE_PREFIXES = {"tb": "tb_pos", "malaria": "malaria_pos", "leukemia": "leukemia_pos"}

# Fixed representative rows for tabular models - used ONLY when a real (non-reference)
# tabular model is actually loaded; these are plain example values, not patient data.
FIXED_TABULAR_ROWS = {
    "diabetes_lab": {"HbA1c_level": 7.8, "blood_glucose_level": 180},
    "diabetes_clinical": {"age": 55, "bmi": 31.0, "hypertension": 1, "heart_disease": 0,
                           "gender": "Female", "smoking_history": "former"},
    "hypertension_clinical": {"age": 60, "bmi": 29.0, "heart_disease": 0,
                               "gender": "Male", "smoking_history": "never"},
}


def decision(score: float, threshold: float) -> str:
    return "FLAG" if score >= threshold else "no flag"


def predict_image(registry: Registry, slot_id: str) -> None:
    samples_dir = registry.artifacts_dir / slot_id / "samples"
    prefix = IMAGE_SAMPLE_PREFIXES.get(slot_id, slot_id)
    candidates = sorted(samples_dir.glob(f"{prefix}*")) if samples_dir.exists() else []
    if not candidates:
        candidates = sorted(samples_dir.glob("*")) if samples_dir.exists() else []
    if not candidates:
        print(f"  [{slot_id}] loaded, but no samples/ image found to predict on - skipping")
        return
    sample = candidates[0]
    raw = sample.read_bytes()
    pred = registry.run_image(slot_id, raw)
    threshold = registry.slots[slot_id].predictor.threshold
    print(f"  [{slot_id}] sample={sample.name} probability={pred['score']:.4f} "
          f"threshold={threshold:.4f} decision={decision(pred['score'], threshold)}")


def predict_tabular(registry: Registry, slot_id: str) -> None:
    row = FIXED_TABULAR_ROWS.get(slot_id)
    if row is None:
        print(f"  [{slot_id}] loaded, but no fixed input defined in this script - skipping")
        return
    pred = registry.run_tabular(slot_id, row)
    threshold = registry.slots[slot_id].predictor.threshold
    print(f"  [{slot_id}] input={row} probability={pred['score']:.4f} "
          f"threshold={threshold:.4f} decision={decision(pred['score'], threshold)}")


def predict_ecg(registry: Registry) -> None:
    values = [0.0] * 187
    pred = registry.run_ecg(values)
    threshold = registry.slots["ecg"].predictor.threshold
    print(f"  [ecg] input=flat 187-sample beat probability={pred['score']:.4f} "
          f"threshold={threshold:.4f} decision={decision(pred['score'], threshold)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", default="artifacts")
    args = ap.parse_args()

    registry = Registry(Path(args.artifacts), BACKEND_DIR / "config")

    print(f"Registry loaded from {Path(args.artifacts).resolve()}\n")
    for slot_id, slot in registry.slots.items():
        if slot.state != "loaded":
            print(f"  [{slot_id}] NOT RUN - state={slot.state} reason={slot.reason}")
            continue
        if slot.kind == "image":
            predict_image(registry, slot_id)
        elif slot.kind == "tabular":
            predict_tabular(registry, slot_id)
        elif slot.kind == "ecg":
            predict_ecg(registry)


if __name__ == "__main__":
    main()
