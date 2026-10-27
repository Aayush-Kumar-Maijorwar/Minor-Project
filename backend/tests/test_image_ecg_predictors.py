import io

import pytest

torch = pytest.importorskip("torch")

from app.predictors.ecg import EcgPredictor, parse_heartbeat
from app.predictors.image import ImagePredictor


def test_image_predictor_loads_fake_checkpoint_and_predicts(fake_artifacts_dir):
    ckpt_path = fake_artifacts_dir / "tb" / "tb_best.pt"
    predictor = ImagePredictor(ckpt_path)
    assert predictor.arch == "tiny_test_cnn"

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(120, 120, 120)).save(buf, format="PNG")
    p = predictor.predict_bytes(buf.getvalue())
    assert 0.0 <= p <= 1.0


def test_ecg_predictor_loads_fake_checkpoint_and_predicts(fake_artifacts_dir):
    ckpt_path = fake_artifacts_dir / "ecg" / "ecg_best.pt"
    predictor = EcgPredictor(ckpt_path)
    assert predictor.input_len == 187

    p = predictor.predict([0.0] * 187)
    assert 0.0 <= p <= 1.0


def test_parse_heartbeat_requires_exactly_187_numbers():
    good = ",".join(["0.1"] * 187).encode()
    assert len(parse_heartbeat(good)) == 187

    bad = ",".join(["0.1"] * 100).encode()
    with pytest.raises(ValueError, match="187-sample heartbeat"):
        parse_heartbeat(bad)
