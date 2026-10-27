"""
Loads whatever model artifacts exist, once, at startup. A missing or corrupt artifact
never raises past here - the slot is marked 'missing'/'error' with a reason, and every
other slot still loads. This is what lets the app start with zero, some, or all model
files present (safety rule #4).
"""
import json
import logging
from pathlib import Path

import sklearn

from .predictors.ecg import EcgPredictor
from .predictors.ecg import TORCH_AVAILABLE as ECG_TORCH_OK
from .predictors.image import ImagePredictor
from .predictors.image import TORCH_AVAILABLE as IMAGE_TORCH_OK
from .predictors.tabular import TabularPredictor

logger = logging.getLogger("medfusion.registry")

IMAGE_SLOTS = {
    "tb": {"modality": "chestXray", "condition": "tuberculosis", "folder": "tb", "prefix": "tb"},
    "malaria": {"modality": "bloodSmearCell", "condition": "malaria", "folder": "malaria", "prefix": "malaria"},
    "leukemia": {"modality": "bloodSmearField", "condition": "leukemia", "folder": "leukemia", "prefix": "leukemia"},
}
TABULAR_SLOTS = {
    "diabetes_lab": {"modality": "lab", "condition": "diabetes"},
    "diabetes_clinical": {"modality": "clinical", "condition": "diabetes"},
    "hypertension_clinical": {"modality": "clinical", "condition": "hypertension"},
}
TABULAR_MODEL_MODALITY = {k: v["modality"] for k, v in TABULAR_SLOTS.items()}


class ModelSlot:
    def __init__(self, slot_id: str, modality: str, condition: str, kind: str):
        self.slot_id = slot_id
        self.modality = modality
        self.condition = condition
        self.kind = kind  # 'image' | 'tabular' | 'ecg'
        self.state = "missing"  # 'loaded' | 'missing' | 'error'
        self.reason: str | None = None
        self.fake = False
        self.model_id = slot_id
        self.predictor = None
        self.meta: dict = {}


class Registry:
    def __init__(self, artifacts_dir: Path, config_dir: Path, min_test_auc: float = 0.65):
        self.artifacts_dir = Path(artifacts_dir)
        self.min_test_auc = min_test_auc
        self.fusion_config = self._load_fusion_config(Path(config_dir))
        self.slots: dict[str, ModelSlot] = {}
        self._load_image_slots()
        self._load_ecg_slot()
        self._load_tabular_slots()
        self._apply_quality_gate()

    # ---- loading -----------------------------------------------------
    @staticmethod
    def _read_json(path: Path) -> dict | None:
        try:
            with open(path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    def _load_fusion_config(self, config_dir: Path) -> dict:
        config = self._read_json(config_dir / "fusion.json") or {}
        override = self._read_json(self.artifacts_dir / "tabular" / "diabetes_fusion.json")
        if override and "diabetes" in config:
            components = [
                {"modality": TABULAR_MODEL_MODALITY[c["model_id"]], "weight": c["weight"]}
                for c in override.get("components", [])
                if c.get("model_id") in TABULAR_MODEL_MODALITY
            ]
            if components:
                config["diabetes"]["components"] = components
            if "fused_threshold" in override:
                config["diabetes"]["fused_threshold"] = override["fused_threshold"]
            config["diabetes"]["weights_source"] = "fitted (artifacts/tabular/diabetes_fusion.json)"
        return config

    def _load_image_slots(self):
        for slot_id, info in IMAGE_SLOTS.items():
            slot = ModelSlot(slot_id, info["modality"], info["condition"], "image")
            folder = self.artifacts_dir / info["folder"]
            ckpt_path = folder / f"{info['prefix']}_best.pt"
            slot.meta = self._read_json(folder / "comparison.json") or {}
            slot.fake = bool(slot.meta.get("fake"))
            if not IMAGE_TORCH_OK:
                slot.state, slot.reason = "missing", "torch not installed"
            elif not ckpt_path.exists():
                slot.state, slot.reason = "missing", "artifact file not found"
            else:
                try:
                    slot.predictor = ImagePredictor(ckpt_path)
                    slot.model_id = f"{info['prefix']}-{slot.predictor.arch}"
                    slot.state = "loaded"
                except Exception as e:  # why: a corrupt/incompatible checkpoint must not crash the app
                    slot.state, slot.reason = "error", str(e)
            self.slots[slot_id] = slot

    def _load_ecg_slot(self):
        slot = ModelSlot("ecg", "ecg", "hypertension", "ecg")
        folder = self.artifacts_dir / "ecg"
        ckpt_path = folder / "ecg_best.pt"
        slot.meta = self._read_json(folder / "comparison.json") or {}
        slot.fake = bool(slot.meta.get("fake"))
        if not ECG_TORCH_OK:
            slot.state, slot.reason = "missing", "torch not installed"
        elif not ckpt_path.exists():
            slot.state, slot.reason = "missing", "artifact file not found"
        else:
            try:
                slot.predictor = EcgPredictor(ckpt_path)
                slot.model_id = f"ecg-{slot.predictor.arch}"
                slot.state = "loaded"
            except Exception as e:
                slot.state, slot.reason = "error", str(e)
        self.slots["ecg"] = slot

    def _load_tabular_slots(self):
        folder = self.artifacts_dir / "tabular"
        for slot_id, info in TABULAR_SLOTS.items():
            slot = ModelSlot(slot_id, info["modality"], info["condition"], "tabular")
            joblib_path = folder / f"{slot_id}_best.joblib"
            slot.meta = self._read_json(folder / f"{slot_id}_comparison.json") or {}
            slot.fake = bool(slot.meta.get("fake"))
            if not joblib_path.exists() or not slot.meta:
                slot.state, slot.reason = "missing", "artifact file not found"
            else:
                try:
                    slot.predictor = TabularPredictor(joblib_path, slot.meta)
                    slot.state = "loaded"
                    if slot.predictor.sklearn_version_mismatch:
                        slot.reason = slot.predictor.sklearn_version_mismatch
                        logger.warning("%s: %s", slot_id, slot.reason)
                except Exception as e:
                    slot.state, slot.reason = "error", str(e)
            self.slots[slot_id] = slot

    def _apply_quality_gate(self):
        """A model that loaded fine can still be refused for inference: below the
        configured test_auc bar, it is downgraded to state='error' with reason
        'below quality gate' - the file exists, but it never predicts (safety rule:
        never feed real patients through a model with no demonstrated signal)."""
        for slot in self.slots.values():
            if slot.state != "loaded":
                continue
            test_auc = self._test_auc(slot)
            if test_auc is not None and test_auc < self.min_test_auc:
                slot.predictor = None
                slot.state = "error"
                slot.reason = f"below quality gate (test_auc={test_auc:.3f} < {self.min_test_auc})"

    # ---- inference -----------------------------------------------------
    @staticmethod
    def _confidence(p: float) -> float:
        return max(p, 1 - p)

    def run_tabular(self, slot_id: str, row: dict) -> dict | None:
        slot = self.slots.get(slot_id)
        if not slot or slot.state != "loaded":
            return None
        result = slot.predictor.predict(row)
        p = result["probability"]
        return {
            "modelId": slot.model_id, "condition": slot.condition, "modality": slot.modality,
            "score": p, "confidence": self._confidence(p), "threshold": slot.predictor.threshold,
            "drivers": result["drivers"], "simulated": slot.fake,
        }

    def run_image(self, slot_id: str, raw_bytes: bytes) -> dict | None:
        slot = self.slots.get(slot_id)
        if not slot or slot.state != "loaded":
            return None
        p = slot.predictor.predict_bytes(raw_bytes)
        return {
            "modelId": slot.model_id, "condition": slot.condition, "modality": slot.modality,
            "score": p, "confidence": self._confidence(p), "threshold": slot.predictor.threshold,
            "simulated": slot.fake,
        }

    def run_ecg(self, values: list[float]) -> dict | None:
        slot = self.slots.get("ecg")
        if not slot or slot.state != "loaded":
            return None
        p = slot.predictor.predict(values)
        return {
            "modelId": slot.model_id, "condition": slot.condition, "modality": slot.modality,
            "score": p, "confidence": self._confidence(p), "threshold": slot.predictor.threshold,
            "simulated": slot.fake,
        }

    # ---- introspection (/health, /models, narrative) --------------------
    def health_models(self) -> list[dict]:
        return [{
            "id": slot.model_id,
            "modality": slot.modality,
            "condition": slot.condition,
            "state": slot.state,
            "reason": slot.reason,
            "simulatedOrFake": slot.fake,
        } for slot in self.slots.values()]

    def versions(self) -> dict:
        out = {"sklearn": sklearn.__version__, "torch": None}
        if IMAGE_TORCH_OK:
            import torch
            out["torch"] = torch.__version__
        return out

    def _slot_folder(self, slot: ModelSlot) -> Path:
        if slot.kind == "tabular":
            return self.artifacts_dir / "tabular"
        if slot.slot_id == "ecg":
            return self.artifacts_dir / "ecg"
        return self.artifacts_dir / IMAGE_SLOTS[slot.slot_id]["folder"]

    def _tuned_metrics(self, slot: ModelSlot) -> dict | None:
        if not slot.meta:
            return None
        selected = slot.meta.get("selected")
        key = "model" if slot.kind == "tabular" else "arch"
        for r in slot.meta.get("results", []):
            if r.get(key) == selected:
                return r.get("tuned")
        return None

    def _test_auc(self, slot: ModelSlot) -> float | None:
        if not slot.meta:
            return None
        selected = slot.meta.get("selected")
        key = "model" if slot.kind == "tabular" else "arch"
        for r in slot.meta.get("results", []):
            if r.get(key) == selected:
                return r.get("test_auc")
        return None

    def narrative_model_meta(self) -> dict:
        out = {}
        for slot in self.slots.values():
            if slot.state != "loaded":
                continue
            tuned = self._tuned_metrics(slot)
            out[slot.model_id] = {
                "sensitivity": tuned.get("sensitivity") if tuned else None,
                "specificity": tuned.get("specificity") if tuned else None,
                "threshold": slot.predictor.threshold,
            }
        return out

    def models_metadata(self) -> list[dict]:
        diabetes_fusion_path = self.artifacts_dir / "tabular" / "diabetes_fusion.json"
        fusion_url = "/static/artifacts/tabular/diabetes_fusion.json" if diabetes_fusion_path.exists() else None

        out = []
        for slot in self.slots.values():
            folder = self._slot_folder(slot)
            comparison_name = "comparison.json" if slot.kind != "tabular" else f"{slot.slot_id}_comparison.json"
            comparison_url = None
            plots = []
            if folder.exists():
                rel = folder.relative_to(self.artifacts_dir).as_posix()
                if (folder / comparison_name).exists():
                    comparison_url = f"/static/artifacts/{rel}/{comparison_name}"
                candidates = ["roc.png", "comparison.png", "confusion_best.png"]
                if slot.kind == "tabular":
                    candidates = [f"{slot.slot_id}_roc.png", f"{slot.slot_id}_comparison.png",
                                  f"{slot.slot_id}_importance.png"]
                for name in candidates:
                    if (folder / name).exists():
                        plots.append(f"/static/artifacts/{rel}/{name}")

            tuned = self._tuned_metrics(slot)
            metrics = None
            if tuned:
                metrics = [
                    {"label": "Sensitivity", "value": f"{tuned['sensitivity']:.0%}", "isPlaceholder": False},
                    {"label": "Specificity", "value": f"{tuned['specificity']:.0%}", "isPlaceholder": False},
                ]
                test_auc = self._test_auc(slot)
                if test_auc is not None:
                    metrics.append({"label": "Test AUC", "value": f"{test_auc:.3f}", "isPlaceholder": False})

            out.append({
                "id": slot.model_id,
                "name": slot.model_id,
                "condition": slot.condition,
                "inputModality": slot.modality,
                "status": "trained_baseline" if slot.state == "loaded" else "planned",
                "version": "v1",
                "lastUpdated": "",
                "explainabilitySupport": slot.kind == "tabular",
                "integrationStatus": "integrated" if slot.state == "loaded" else "mock",
                "metrics": metrics,
                "plots": plots or None,
                "comparisonUrl": comparison_url,
                "fusionUrl": fusion_url if slot.condition == "diabetes" else None,
                "fake": slot.fake,
            })
        return out
