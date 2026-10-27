"""
Generates clearly-labelled PLACEHOLDER images and ECG CSVs into public/demo/ so the
demo-case picker (Phase 3 Part D) works end-to-end right now, against fake artifacts,
before any real Kaggle samples are imported with import_demo_samples.py.

Every image is stamped "PLACEHOLDER - NOT A REAL <X>" so nobody mistakes it for a real
clinical image. Run with the backend's venv Python (it already has Pillow):

    backend\\.venv\\Scripts\\python.exe scripts\\make_placeholder_demo.py
"""
import csv
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "public" / "demo"

IMAGES = [
    ("chest_xray_positive.png", "PLACEHOLDER\nNOT A REAL X-RAY\n(synthetic - positive)", (40, 40, 60)),
    ("chest_xray_negative.png", "PLACEHOLDER\nNOT A REAL X-RAY\n(synthetic - negative)", (40, 60, 40)),
    ("smear_cell_positive.png", "PLACEHOLDER\nNOT A REAL CELL IMAGE\n(synthetic - positive)", (60, 30, 30)),
    ("smear_cell_negative.png", "PLACEHOLDER\nNOT A REAL CELL IMAGE\n(synthetic - negative)", (30, 55, 30)),
    ("smear_field_positive.png", "PLACEHOLDER\nNOT A REAL SMEAR FIELD\n(synthetic - positive)", (60, 30, 50)),
    ("smear_field_negative.png", "PLACEHOLDER\nNOT A REAL SMEAR FIELD\n(synthetic - negative)", (30, 50, 55)),
]

ECGS = [
    ("ecg_normal.csv", False),
    ("ecg_abnormal.csv", True),
]


def _make_image(name: str, label: str, bg: tuple, seed: int):
    rng = random.Random(seed)
    size = (256, 256)
    img = Image.new("RGB", size, color=bg)
    # light synthetic noise texture so it isn't a flat rectangle
    px = img.load()
    for _ in range(2000):
        x, y = rng.randrange(size[0]), rng.randrange(size[1])
        shade = rng.randrange(-20, 20)
        r, g, b = px[x, y]
        px[x, y] = (max(0, min(255, r + shade)), max(0, min(255, g + shade)), max(0, min(255, b + shade)))

    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    lines = label.split("\n")
    y = 90
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((size[0] - w) / 2, y), line, fill=(255, 255, 255), font=font)
        y += 20

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(OUT_DIR / name)
    print(f"  wrote {name}")


def _make_ecg(name: str, abnormal: bool, seed: int):
    rng = random.Random(seed)
    # A crude synthetic "heartbeat": a smooth baseline plus a sharp spike (QRS-like),
    # wider/noisier when "abnormal". Not real ECG data - placeholder only.
    values = []
    spike_center = 60
    spike_width = 25 if abnormal else 10
    for i in range(187):
        baseline = 0.05 * rng.uniform(-1, 1)
        dist = abs(i - spike_center)
        spike = max(0.0, 1.0 - dist / spike_width) if dist < spike_width else 0.0
        noise = 0.08 * rng.uniform(-1, 1) if abnormal else 0.02 * rng.uniform(-1, 1)
        values.append(round(baseline + spike + noise, 4))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / name, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(values)
    print(f"  wrote {name}")


def main():
    print(f"Writing placeholder demo assets to {OUT_DIR}")
    for i, (name, label, bg) in enumerate(IMAGES):
        _make_image(name, label, bg, seed=i)
    for i, (name, abnormal) in enumerate(ECGS):
        _make_ecg(name, abnormal, seed=100 + i)
    print("Done. These are NOT real medical images/signals - placeholders only.")


if __name__ == "__main__":
    main()
