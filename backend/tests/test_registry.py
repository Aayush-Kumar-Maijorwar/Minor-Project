import json
import shutil
import sys
from pathlib import Path

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
    assert len(registry.slots) == 7  # tb, malaria, leukemia, ecg, diabetes_lab, diabetes_clinical, hypertension_clinical
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
