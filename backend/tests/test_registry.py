import json
import shutil
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.registry import Registry  # noqa: E402


def test_missing_model_file_is_reported_not_crashed(tmp_path, fake_artifacts_dir):
    # Copy the fake artifacts but delete the tb folder entirely - the registry must still
    # construct cleanly and report that one slot as missing with a reason.
    artifacts = tmp_path / "artifacts"
    shutil.copytree(fake_artifacts_dir, artifacts)
    shutil.rmtree(artifacts / "tb", ignore_errors=True)  # no-op if torch wasn't installed (tb/ was never created)

    config_dir = BACKEND_DIR / "config"
    registry = Registry(artifacts, config_dir)

    tb_slot = registry.slots["tb"]
    assert tb_slot.state == "missing"
    assert tb_slot.reason

    tb_health = next(m for m in registry.health_models() if m["modality"] == "chestXray")
    assert tb_health["state"] == "missing"
    assert tb_health["reason"]


def test_app_starts_with_zero_artifacts(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    registry = Registry(empty, BACKEND_DIR / "config")
    assert len(registry.slots) == 8  # tb, malaria, leukemia, ecg, diabetes_lab, diabetes_clinical, hypertension_clinical, diabetes_combined
    for slot in registry.slots.values():
        assert slot.state in ("missing", "error")
        assert slot.reason


def test_sklearn_version_mismatch_is_surfaced_as_a_warning_not_an_error(tmp_path, fake_artifacts_dir):
    artifacts = tmp_path / "artifacts"
    shutil.copytree(fake_artifacts_dir, artifacts)
    meta_path = artifacts / "tabular" / "diabetes_lab_comparison.json"
    meta = json.loads(meta_path.read_text())
    meta["sklearn_version"] = "0.0.0-not-the-real-version"
    meta_path.write_text(json.dumps(meta))

    registry = Registry(artifacts, BACKEND_DIR / "config")
    slot = registry.slots["diabetes_lab"]
    assert slot.state == "loaded"  # a version mismatch is a warning, not a load failure
    assert slot.reason and "0.0.0-not-the-real-version" in slot.reason


def test_diabetes_fusion_json_override_is_picked_up(fake_artifacts_dir):
    registry = Registry(fake_artifacts_dir, BACKEND_DIR / "config")
    components = {c["modality"]: c["weight"] for c in registry.fusion_config["diabetes"]["components"]}
    assert abs(components["lab"] - 0.6) < 1e-9
    assert abs(components["clinical"] - 0.4) < 1e-9


def test_quality_gate_refuses_a_model_below_min_test_auc(tmp_path, fake_artifacts_dir):
    # A model whose own comparison.json reports test_auc below the gate must load the
    # file successfully but still be refused for inference - state='error', reason
    # naming the quality gate, never silently used to predict on real patients.
    artifacts = tmp_path / "artifacts"
    shutil.copytree(fake_artifacts_dir, artifacts)
    meta_path = artifacts / "tabular" / "diabetes_lab_comparison.json"
    meta = json.loads(meta_path.read_text())
    for r in meta["results"]:
        r["test_auc"] = 0.50  # below the 0.65 gate, e.g. a randomly-generated-looking dataset
    meta_path.write_text(json.dumps(meta))

    registry = Registry(artifacts, BACKEND_DIR / "config", min_test_auc=0.65)
    slot = registry.slots["diabetes_lab"]
    assert slot.state == "error"
    assert "quality gate" in slot.reason
    assert slot.predictor is None
    assert registry.run_tabular("diabetes_lab", {}) is None  # refused, not silently run


def test_quality_gate_accepts_a_model_at_or_above_min_test_auc(fake_artifacts_dir):
    registry = Registry(fake_artifacts_dir, BACKEND_DIR / "config", min_test_auc=0.65)
    slot = registry.slots["diabetes_lab"]
    assert slot.state == "loaded"  # fake artifacts report test_auc=0.7, above the gate


def test_loading_a_real_format_image_checkpoint(tmp_path):
    """Generates a TINY checkpoint using a real supported arch (not the test-only
    tiny_test_cnn) with the exact real contract keys, and confirms the registry loads
    it through the normal _build_model() path used for real trained weights."""
    pytest.importorskip("torch")
    import torch
    import torch.nn as nn
    from torchvision import models

    m = models.mobilenet_v3_small(weights=None)
    m.classifier[-1] = nn.Linear(m.classifier[-1].in_features, 1)

    artifacts = tmp_path / "artifacts"
    (artifacts / "tb").mkdir(parents=True)
    torch.save(
        dict(disease="tb", arch="mobilenet_v3_small", state_dict=m.state_dict(), img_size=224,
             threshold=0.87, mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225],
             classes=["negative", "positive"], metrics={"sensitivity": 0.95, "specificity": 0.9},
             test_auc=0.93),
        artifacts / "tb" / "tb_best.pt",
    )
    (artifacts / "tb" / "comparison.json").write_text(json.dumps({
        "disease": "tb", "selected": "mobilenet_v3_small",
        "results": [{"arch": "mobilenet_v3_small", "test_auc": 0.93, "tuned": {"sensitivity": 0.95, "specificity": 0.9}}],
    }))

    registry = Registry(artifacts, BACKEND_DIR / "config", min_test_auc=0.65)
    slot = registry.slots["tb"]
    assert slot.state == "loaded"
    assert slot.model_id == "tb-mobilenet_v3_small"
    assert slot.predictor.threshold == 0.87
