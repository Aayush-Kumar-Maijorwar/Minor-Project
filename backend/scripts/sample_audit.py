"""
Phase 2 step 1: runs EVERY held-out test image in artifacts/{tb,malaria}/samples/
through its real model (never a placeholder/fake image) and reports probability,
threshold, and decision against the true label carried in the file name
(_pos_/_neg_). A flagged negative is a false alarm; an unflagged positive is a miss.

Usage (from backend/, venv active):
    python scripts/sample_audit.py [--artifacts artifacts]
"""
import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.registry import Registry  # noqa: E402

SAMPLE_DISEASES = {"tb": "tb", "malaria": "malaria"}


def true_label(filename: str) -> str:
    if "_pos_" in filename:
        return "positive"
    if "_neg_" in filename:
        return "negative"
    return "unknown"


def audit_disease(registry: Registry, slot_id: str) -> list[dict]:
    samples_dir = registry.artifacts_dir / slot_id / "samples"
    rows = []
    if not samples_dir.exists():
        print(f"\n[{slot_id}] samples/ folder MISSING at {samples_dir} - skipping (no placeholder images used)")
        return rows

    if registry.slots[slot_id].state != "loaded":
        print(f"\n[{slot_id}] model not loaded (state={registry.slots[slot_id].state}) - skipping")
        return rows

    threshold = registry.slots[slot_id].predictor.threshold
    print(f"\n[{slot_id}] threshold={threshold:.4f}")
    print(f"  {'file':<20} {'true_label':<10} {'probability':<12} {'decision':<10} {'result'}")
    for sample in sorted(samples_dir.glob("*")):
        raw = sample.read_bytes()
        pred = registry.run_image(slot_id, raw)
        label = true_label(sample.name)
        decision = "FLAG" if pred["score"] >= threshold else "no flag"
        if label == "positive":
            result = "HIT" if decision == "FLAG" else "MISS"
        elif label == "negative":
            result = "false alarm" if decision == "FLAG" else "correct"
        else:
            result = "?"
        print(f"  {sample.name:<20} {label:<10} {pred['score']:<12.4f} {decision:<10} {result}")
        rows.append({"file": sample.name, "true_label": label, "probability": pred["score"],
                      "threshold": threshold, "decision": decision, "result": result,
                      "disagrees": result in ("MISS", "false alarm")})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", default="artifacts")
    args = ap.parse_args()

    registry = Registry(Path(args.artifacts), BACKEND_DIR / "config")
    all_rows = {}
    for slot_id in SAMPLE_DISEASES:
        all_rows[slot_id] = audit_disease(registry, slot_id)

    print("\n--- Disagreements (model vs ground truth) ---")
    any_disagreement = False
    for slot_id, rows in all_rows.items():
        for r in rows:
            if r["disagrees"]:
                any_disagreement = True
                print(f"  [{slot_id}] {r['file']}: true={r['true_label']} decision={r['decision']} "
                      f"probability={r['probability']:.4f}")
    if not any_disagreement:
        print("  none - every sample's decision matches its ground-truth label")


if __name__ == "__main__":
    main()
