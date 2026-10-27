# Training scripts (Kaggle)

These three scripts produce the model artifacts the backend loads from `backend/artifacts/`.
They do not run in this repo's normal dev environment - run them on Kaggle (free GPU) and copy
the output folders into `backend/artifacts/`.

## Setup (once per notebook)

1. Create a new Kaggle Notebook.
2. Under **Add Data**, attach the dataset(s) you need (see per-script notes below).
3. In the notebook settings: **Accelerator -> GPU**, **Internet -> On** (needed for pretrained
   ImageNet weights the first time).
4. Upload `train_image.py`, `train_tabular.py`, `train_ecg.py` as notebook files, or paste their
   contents into a cell.

## train_image.py - TB / malaria / leukemia (image models)

Datasets (attach whichever disease you're training):
- Tuberculosis: a chest X-ray dataset with `Tuberculosis/` and `Normal/` folders.
- Malaria: the NIH malaria cell dataset (`Parasitized/` / `Uninfected/`).
- Leukemia: a blood-smear dataset with a `benign` class and `[Malignant] ...` subtype folders.

```bash
python train_image.py --disease tb --smoke        # quick pipeline check first
python train_image.py --disease tb
python train_image.py --disease malaria
python train_image.py --disease leukemia
```

Output per disease (under `--out`, default `/kaggle/working/medfusion/<disease>/`):
`<disease>_best.pt`, `comparison.json`, `comparison.csv`, `roc.png`, `comparison.png`,
`confusion_best.png`.

Copy each disease folder to `backend/artifacts/<disease>/` (disease folder names: `tb`,
`malaria`, `leukemia`).

## train_tabular.py - diabetes / hypertension (tabular models)

Dataset: Kaggle "diabetes-prediction-dataset" (iammustafatz), CSV columns `gender, age,
hypertension, heart_disease, smoking_history, bmi, HbA1c_level, blood_glucose_level, diabetes`.

```bash
python train_tabular.py --csv /kaggle/input/.../diabetes_prediction_dataset.csv
```

Trains four tasks, one per deployed modality-model plus one reference-only model:

| task (= model id)      | columns used                                              | used at inference? |
|-------------------------|------------------------------------------------------------|---------------------|
| `diabetes_lab`           | HbA1c_level, blood_glucose_level                            | yes (lab modality) |
| `diabetes_clinical`      | gender, smoking_history, age, bmi, hypertension, heart_disease | yes (clinical modality) |
| `hypertension_clinical`  | gender, smoking_history, age, bmi, heart_disease            | yes (clinical modality) |
| `diabetes_combined`      | every column above                                          | **no** - reference only, for slides |

Output per task (under `--out`, default `/kaggle/working/medfusion/tabular/`):
`<task>_best.joblib`, `<task>_comparison.json`, `<task>_comparison.csv`, `<task>_roc.png`,
`<task>_comparison.png`, and `<task>_importance.png` for tree-based winners.

Copy the whole folder to `backend/artifacts/tabular/`.

### Optional: `diabetes_fusion.json`

If you want the backend to use fitted fusion weights for diabetes (instead of the 0.5/0.5
default in `backend/config/fusion.json`), fit `diabetes_lab` + `diabetes_clinical` together on
the validation split and write `backend/artifacts/tabular/diabetes_fusion.json` by hand or with
a small notebook cell, shaped like:

```json
{
  "components": [
    {"model_id": "diabetes_lab", "weight": 0.6},
    {"model_id": "diabetes_clinical", "weight": 0.4}
  ],
  "fused_threshold": 0.5
}
```

This is optional - without it the backend falls back to the defaults in `fusion.json`.

## train_ecg.py - ECG cardiac-abnormality screen (supporting signal for hypertension)

Dataset: Kaggle "ECG Heartbeat Categorization Dataset" (shayanfazeli/heartbeat),
`mitbih_train.csv` / `mitbih_test.csv` - each row is one heartbeat resampled to 187 samples
plus a trailing MIT-BIH class label. We binarize: class 0 = normal, classes 1-4 = abnormal.

```bash
python train_ecg.py --smoke        # quick pipeline check first
python train_ecg.py
```

Output (under `--out`, default `/kaggle/working/medfusion/ecg/`): `ecg_best.pt`,
`comparison.json`, `comparison.csv`, `roc.png`, `comparison.png`, `confusion_best.png`.

Copy the folder to `backend/artifacts/ecg/`.

**This model is a supporting cardiac-abnormality signal only, not a hypertension-specific
test** - it is fused with `hypertension_clinical` at a low weight (see
`backend/config/fusion.json`) and the narrative always labels it as such.

## After copying artifacts in

`backend/artifacts/` is gitignored for the large binary files (`*.pt`, `*.joblib`) and for
`backend/data/` (runtime patient/analysis store) - `comparison.json`/`.csv` and `.png` plots
stay committable so they can be checked in for the presentation. See `backend/README.md` for
how the backend loads these and what happens when some (or all) are missing.
