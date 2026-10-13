"""
Step 0 of Phase 3: verify the training scripts actually produce what the backend
registry expects, by running the REAL scripts (not a mock) against tiny synthetic
stand-ins shaped like the real Kaggle datasets, then loading the outputs through the
real registry/predictors and running a prediction.

Marked 'slow' (real subprocess training runs, even tiny/smoke). Skipped outright if
torch isn't installed, since the image/ECG scripts need it.
"""
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("torch")

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
TRAINING_DIR = REPO_ROOT / "training"

pytestmark = pytest.mark.slow


def _run(args: list[str], cwd: Path):
    result = subprocess.run([sys.executable, *args], cwd=cwd, capture_output=True, text=True, timeout=900)
    assert result.returncode == 0, (
        f"command failed: {' '.join(args)}\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    return result


# ---------------------------------------------------------------------------
# Tabular
# ---------------------------------------------------------------------------
def _write_fake_diabetes_csv(path: Path, n_per_class: int = 30):
    rows = []
    import random
    rng = random.Random(42)
    for diabetes in (0, 1):
        for _ in range(n_per_class):
            row = {
                "gender": rng.choice(["Male", "Female"]),
                "age": rng.uniform(18, 85),
                "hypertension": rng.choice([0, 1]),
                "heart_disease": rng.choice([0, 1]),
                "smoking_history": rng.choice(["never", "former", "current", "No Info"]),
                "bmi": rng.uniform(16, 45),
                "HbA1c_level": rng.uniform(7.5, 10) if diabetes else rng.uniform(4, 6),
                "blood_glucose_level": rng.uniform(180, 300) if diabetes else rng.uniform(70, 140),
                "diabetes": diabetes,
            }
            rows.append(row)
    # a few EXACT duplicate rows - the script must drop these (see main()'s drop_duplicates)
    rows.append(dict(rows[0]))
    rows.append(dict(rows[0]))

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_tabular_training_contract(tmp_path):
    csv_path = tmp_path / "diabetes_prediction_dataset.csv"
    _write_fake_diabetes_csv(csv_path)
    out_dir = tmp_path / "tabular_out"

    _run(["training/train_tabular.py", "--csv", str(csv_path), "--out", str(out_dir)], cwd=REPO_ROOT)

    from app.predictors.tabular import TabularPredictor

    for task in ("diabetes_lab", "diabetes_clinical", "hypertension_clinical", "diabetes_combined"):
        joblib_path = out_dir / f"{task}_best.joblib"
        meta_path = out_dir / f"{task}_comparison.json"
        assert joblib_path.exists(), f"{task}: missing joblib output"
        assert meta_path.exists(), f"{task}: missing comparison.json"

        meta = json.loads(meta_path.read_text())
        for field in ("features", "threshold", "selected", "results"):
            assert field in meta, f"{task}: comparison.json missing '{field}' the backend reads"

        predictor = TabularPredictor(joblib_path, meta)
        assert predictor.threshold == meta["threshold"]

        row = {f: (1 if f in ("hypertension", "heart_disease") else
                    ("Female" if f == "gender" else "never" if f == "smoking_history" else 50.0))
               for f in predictor.features}
        result = predictor.predict(row)
        assert 0.0 <= result["probability"] <= 1.0

    # diabetes_fusion.json isn't produced by the script (it's a hand-fitted, optional
    # override per training/README.md) - write one as the README instructs and confirm
    # the registry actually applies it.
    fusion_override = {
        "components": [
            {"model_id": "diabetes_lab", "weight": 0.7},
            {"model_id": "diabetes_clinical", "weight": 0.3},
        ],
        "fused_threshold": 0.45,
    }
    (out_dir / "diabetes_fusion.json").write_text(json.dumps(fusion_override))

    artifacts_dir = tmp_path / "artifacts"
    (artifacts_dir / "tabular").mkdir(parents=True)
    for p in out_dir.glob("diabetes_lab_*"):
        (artifacts_dir / "tabular" / p.name).write_bytes(p.read_bytes())
    for p in out_dir.glob("diabetes_clinical_*"):
        (artifacts_dir / "tabular" / p.name).write_bytes(p.read_bytes())
    (artifacts_dir / "tabular" / "diabetes_fusion.json").write_text(json.dumps(fusion_override))

    from app.registry import Registry

    registry = Registry(artifacts_dir, BACKEND_DIR / "config")
    components = {c["modality"]: c["weight"] for c in registry.fusion_config["diabetes"]["components"]}
    assert abs(components["lab"] - 0.7) < 1e-9
    assert abs(components["clinical"] - 0.3) < 1e-9
    assert registry.fusion_config["diabetes"]["fused_threshold"] == 0.45


# ---------------------------------------------------------------------------
# Image (TB / malaria / leukemia)
# ---------------------------------------------------------------------------
def _write_tiny_png(path: Path, size=(48, 48), seed=0):
    from PIL import Image
    import random

    rng = random.Random(seed)
    img = Image.new("RGB", size)
    pixels = [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(size[0] * size[1])]
    img.putdata(pixels)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def _build_tb_dataset(root: Path, n_per_class=12):
    base = root / "tuberculosis-tb-chest-xray-dataset" / "TB_Chest_Radiography_Database"
    for cls, label_dir in (("Normal", "Normal"), ("Tuberculosis", "Tuberculosis")):
        for i in range(n_per_class):
            _write_tiny_png(base / label_dir / f"{cls}-{i}.png", seed=i)
    return base


def _build_malaria_dataset(root: Path, n_per_class=12):
    base = root / "cell-images-for-detecting-malaria" / "cell_images"
    for cls, label_dir in (("Parasitized", "Parasitized"), ("Uninfected", "Uninfected")):
        for i in range(n_per_class):
            name = f"C{i}P{i}ThinF_IMG_2020_cell_{i}.png" if i % 2 == 0 else f"C{i}_thinF_IMG_2020_cell_{i}.png"
            _write_tiny_png(base / label_dir / name, seed=i + 100)
    return base


def _build_leukemia_dataset(root: Path, n_per_class=12):
    base = root / "blood-cell-cancer-all-4class" / "Original"
    malignant_subtypes = ["[Malignant] early Pre-B", "[Malignant] Pre-B", "[Malignant] Pro-B"]
    for i in range(n_per_class):
        _write_tiny_png(base / "Benign" / f"benign-{i}.png", seed=i + 200)
    for i in range(n_per_class):
        sub = malignant_subtypes[i % len(malignant_subtypes)]
        _write_tiny_png(base / sub / f"mal-{i}.png", seed=i + 300)
    return base


@pytest.mark.parametrize("disease,builder", [
    ("tb", _build_tb_dataset),
    ("malaria", _build_malaria_dataset),
    ("leukemia", _build_leukemia_dataset),
])
def test_image_training_contract(tmp_path, disease, builder):
    root = builder(tmp_path / f"{disease}_data")
    out_dir = tmp_path / f"{disease}_out"

    _run([
        "training/train_image.py", "--disease", disease, "--root", str(root), "--out", str(tmp_path / "out"),
        "--smoke", "--no_pretrained", "--archs", "resnet18", "mobilenet_v3_small",
    ], cwd=REPO_ROOT)

    produced = tmp_path / "out" / disease
    ckpt_path = produced / f"{disease}_best.pt"
    meta_path = produced / "comparison.json"
    assert ckpt_path.exists(), f"{disease}: missing checkpoint"
    assert meta_path.exists(), f"{disease}: missing comparison.json"

    import torch
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    for field in ("disease", "arch", "state_dict", "img_size", "threshold", "mean", "std", "classes", "metrics", "test_auc"):
        assert field in ckpt, f"{disease}: checkpoint missing '{field}' the backend predictor reads"

    from app.predictors.image import ImagePredictor
    predictor = ImagePredictor(ckpt_path)
    assert predictor.threshold == ckpt["threshold"]

    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(100, 100, 100)).save(buf, format="PNG")
    p = predictor.predict_bytes(buf.getvalue())
    assert 0.0 <= p <= 1.0

    meta = json.loads(meta_path.read_text())
    for field in ("selected", "results"):
        assert field in meta, f"{disease}: comparison.json missing '{field}'"

    samples_dir = produced / "samples"
    assert samples_dir.exists() and any(samples_dir.iterdir()), f"{disease}: samples/ missing or empty"


# ---------------------------------------------------------------------------
# ECG
# ---------------------------------------------------------------------------
def _write_ptb_csv(path: Path, n_rows: int, label: int, seed: int):
    import random
    rng = random.Random(seed)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        for _ in range(n_rows):
            beat = [rng.uniform(-1, 1) for _ in range(187)]
            writer.writerow(beat + [label])


def test_ecg_training_contract(tmp_path):
    root = tmp_path / "ecg_data"
    root.mkdir()
    _write_ptb_csv(root / "ptbdb_normal.csv", 30, label=0, seed=1)
    _write_ptb_csv(root / "ptbdb_abnormal.csv", 30, label=1, seed=2)
    out_dir = tmp_path / "ecg_out"

    _run(["training/train_ecg.py", "--root", str(root), "--out", str(out_dir), "--smoke"], cwd=REPO_ROOT)

    ckpt_path = out_dir / "ecg_best.pt"
    meta_path = out_dir / "comparison.json"
    assert ckpt_path.exists()
    assert meta_path.exists()

    import torch
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    for field in ("arch", "state_dict", "input_len", "threshold", "classes", "metrics", "test_auc"):
        assert field in ckpt, f"ecg: checkpoint missing '{field}' the backend predictor reads"
    assert ckpt["input_len"] == 187

    from app.predictors.ecg import EcgPredictor
    predictor = EcgPredictor(ckpt_path)
    assert predictor.threshold == ckpt["threshold"]
    p = predictor.predict([0.0] * 187)
    assert 0.0 <= p <= 1.0

    samples_dir = out_dir / "samples"
    assert samples_dir.exists() and any(samples_dir.iterdir()), "ecg: samples/ missing or empty"
