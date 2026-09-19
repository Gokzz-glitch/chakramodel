# Notebook pair: Kvasir-SEG + CVC-ClinicDB

Timestamp: 2026-09-19 19:45 UTC

This notebook pair is the first clean research run for the Transformer U-Net pilot.

## Pair contents
- `Kaggle_XAttnUNet_Audit.ipynb`: audits mounted datasets and identifies the clean image/mask candidates.
- `Kaggle_XAttnUNet_Pilot.ipynb`: sets the selected dataset paths and runs the smoke training on the chosen pair.

## Selected source paths
```python
TRAIN_IMAGES = "/kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/kvasir-seg/images"
TRAIN_MASKS = "/kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/kvasir-seg/masks"
VAL_IMAGES = "/kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/cvc-clinicdb/images"
VAL_MASKS = "/kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/cvc-clinicdb/masks"
```

## History rules
- Keep one notebook per dataset pair and one README per timestamped run.
- Store the exact date/time and selected dataset paths for reproducibility.
- Do not mix video-only sources into the supervised training pair.
