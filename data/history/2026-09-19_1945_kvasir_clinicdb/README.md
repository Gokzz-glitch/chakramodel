# Dataset pair: Kvasir-SEG + CVC-ClinicDB

Timestamp: 2026-09-19 19:45 UTC

This pair was selected as the first scientifically valid research split for the Transformer U-Net pilot.

## Why this pair
- Kvasir-SEG gives the primary training set with matched image-mask pairs.
- CVC-ClinicDB gives a separate validation set with a different acquisition style for domain checking.
- Both are already present in the Kaggle audit under `datasets/gokulrocky/chakramodel-evaluation-datasets`.

## Training split
- Primary train: `kvasir-seg/images` + `kvasir-seg/masks`
- Validation: `cvc-clinicdb/images` + `cvc-clinicdb/masks`
- External test: `CVC-300` or `PolypDB` after the first pilot passes
- False-positive check: `ldpolypvideowithoutpolyps`

## Leakage rules
- Never split frames from the same video into train and validation.
- Use patient/video-level grouping when the source is temporal.
- Keep the audit output from the paired Kaggle notebook as the source of truth for dataset history.

## Commands used
```bash
python data/scripts/prepare_segmentation_manifest.py \
  --images /kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/kvasir-seg/images \
  --masks /kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/kvasir-seg/masks \
  --output /kaggle/working/prepared_kvasir \
  --materialize

python data/scripts/prepare_segmentation_manifest.py \
  --images /kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/cvc-clinicdb/images \
  --masks /kaggle/input/datasets/gokulrocky/chakramodel-evaluation-datasets/cvc-clinicdb/masks \
  --output /kaggle/working/prepared_clinicdb \
  --materialize
```
