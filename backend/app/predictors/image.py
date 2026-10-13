"""
Image (chest X-ray / blood smear) predictor. torch/torchvision are imported lazily -
if they are not installed, TORCH_AVAILABLE is False, the module still imports cleanly,
and ImagePredictor() raises a clean RuntimeError the registry turns into "torch not
installed" instead of crashing the app.
"""
from io import BytesIO
from pathlib import Path

from PIL import Image

try:
    import torch
    import torch.nn as nn
    from torchvision import models, transforms

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None  # type: ignore[assignment]

IMAGENET_MEAN, IMAGENET_STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]

if TORCH_AVAILABLE:
    class TinyTestCnn(nn.Module):
        """Not a real architecture - used only by scripts/make_fake_artifacts.py so fake
        checkpoints stay a few KB instead of a full ResNet's tens of MB. Never produced
        by training/train_image.py."""

        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(nn.Conv2d(3, 4, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool2d(1))
            self.head = nn.Linear(4, 1)

        def forward(self, x):
            return self.head(self.net(x).flatten(1))


def _build_model(arch: str):
    if arch == "tiny_test_cnn":
        return TinyTestCnn()
    m = getattr(models, arch)(weights=None)
    if arch == "resnet18":
        m.fc = nn.Linear(m.fc.in_features, 1)
    elif arch == "densenet121":
        m.classifier = nn.Linear(m.classifier.in_features, 1)
    elif arch in ("efficientnet_b0", "mobilenet_v3_small"):
        m.classifier[-1] = nn.Linear(m.classifier[-1].in_features, 1)
    else:
        raise ValueError(f"unknown arch {arch!r}")
    return m


class ImagePredictor:
    def __init__(self, checkpoint_path: Path):
        if not TORCH_AVAILABLE:
            raise RuntimeError("torch not installed")
        ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        self.disease: str = ckpt["disease"]
        self.arch: str = ckpt["arch"]
        self.img_size: int = ckpt["img_size"]
        self.threshold: float = ckpt["threshold"]
        self.mean, self.std = ckpt.get("mean", IMAGENET_MEAN), ckpt.get("std", IMAGENET_STD)
        self.metrics: dict = ckpt.get("metrics", {})
        self.test_auc = ckpt.get("test_auc")

        self.model = _build_model(self.arch)
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()
        self.transform = transforms.Compose([
            transforms.Resize((self.img_size, self.img_size)),
            transforms.ToTensor(),
            transforms.Normalize(self.mean, self.std),
        ])

    def predict_bytes(self, raw: bytes) -> float:
        image = Image.open(BytesIO(raw)).convert("RGB")
        x = self.transform(image).unsqueeze(0)
        with torch.no_grad():
            logit = self.model(x).squeeze(1)
            return float(torch.sigmoid(logit).item())
