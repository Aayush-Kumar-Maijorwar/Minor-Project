"""
ECG (single 187-sample heartbeat) predictor. The three model classes below are copied
VERBATIM from training/train_ecg.py so a saved state_dict loads unchanged - do not edit
one without the other. torch is imported lazily (see image.py for why).
"""
from pathlib import Path

try:
    import torch
    import torch.nn as nn

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None  # type: ignore[assignment]

INPUT_LEN = 187

if TORCH_AVAILABLE:
    # --- copied verbatim from training/train_ecg.py ---
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
            x = x.transpose(1, 2)
            _, h = self.gru(x)
            h = torch.cat([h[0], h[1]], dim=-1)
            return self.head(h)

    ARCHS = {"cnn1d_small": Cnn1dSmall, "cnn1d_residual": Cnn1dResidual, "bigru": BiGru}
    # --- end verbatim copy ---
else:
    ARCHS = {}


def parse_heartbeat(raw: bytes) -> list[float]:
    """CSV/TXT with any delimiter, or .npy. Raises ValueError if not exactly 187 numbers."""
    try:
        import numpy as np
        import io

        try:
            arr = np.load(io.BytesIO(raw), allow_pickle=False)
            values = [float(v) for v in np.asarray(arr).ravel()]
        except Exception:
            text = raw.decode("utf-8", errors="ignore")
            for sep in (",", "\t", " ", ";", "\n"):
                text = text.replace(sep, ",")
            values = [float(v) for v in text.split(",") if v.strip() != ""]
    except Exception as e:
        raise ValueError(f"could not parse ECG data: {e}") from e

    if len(values) != INPUT_LEN:
        raise ValueError("ECG must be a single 187-sample heartbeat")
    return values


class EcgPredictor:
    def __init__(self, checkpoint_path: Path):
        if not TORCH_AVAILABLE:
            raise RuntimeError("torch not installed")
        ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        self.arch: str = ckpt["arch"]
        self.input_len: int = ckpt.get("input_len", INPUT_LEN)
        self.threshold: float = ckpt["threshold"]
        self.metrics: dict = ckpt.get("metrics", {})
        self.test_auc = ckpt.get("test_auc")

        self.model = ARCHS[self.arch]()
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()

    def predict(self, values: list[float]) -> float:
        x = torch.tensor(values, dtype=torch.float32).view(1, 1, -1)
        with torch.no_grad():
            logit = self.model(x).squeeze(1)
            return float(torch.sigmoid(logit).item())
