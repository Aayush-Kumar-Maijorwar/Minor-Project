# Demo image attribution

The 4 images in `public/demo/images/` are REAL held-out test samples copied from
`backend/artifacts/{tb,malaria}/samples/` (see `backend/scripts/sample_audit.py` for
the audit that selected them - every sample's model decision matched its ground-truth
label, so no "hard case" was needed). They are not synthetic or placeholder images.

| File | Disease | Ground truth | Dataset | Kaggle link |
|---|---|---|---|---|
| `tb_xray_positive.png` | Tuberculosis | positive | chest X-ray dataset with `Tuberculosis/` / `Normal/` folders (see `training/train_image.py`) | TODO: fill in the exact Kaggle dataset URL used to train `tb` |
| `tb_xray_negative.png` | Tuberculosis | negative | same as above | same as above |
| `malaria_cell_positive.png` | Malaria | positive | NIH malaria cell dataset (`Parasitized/` / `Uninfected/` folders, see `training/train_image.py`) | TODO: fill in the exact Kaggle dataset URL used to train `malaria` |
| `malaria_cell_negative.png` | Malaria | negative | same as above | same as above |

**License: VERIFY before public release.** This repo does not record the exact Kaggle
dataset slug/URL used for training - fill in the two TODOs above with the dataset page
you actually downloaded from on Kaggle, and confirm its license permits redistributing
these 4 sample images in a public demo, before sharing this repo publicly.
