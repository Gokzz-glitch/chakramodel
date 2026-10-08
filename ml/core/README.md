# Core

> Shared ML library reused by every clinical task.

| | |
|---|---|
| Path | `ml/core/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Confidential |
| Change control | Free-form for experiments; CONTROLLED for anything in a released model |

## What belongs here

Shared ML library reused by every clinical task.

## What does NOT belong here

- Task-specific code.

## Contents

| Folder | Purpose |
|---|---|
| [`data-loading/`](data-loading/README.md) | Dataset readers that consume curated releases via manifests. |
| [`augmentation/`](augmentation/README.md) | Image/video augmentation with clinically plausible transforms. |
| [`metrics/`](metrics/README.md) | Metrics (detection, segmentation, classification, survival) with tests. |
| [`calibration/`](calibration/README.md) | Probability calibration and threshold selection tools. |
| [`uncertainty/`](uncertainty/README.md) | Uncertainty estimation and out-of-distribution detection. |
| [`explainability/`](explainability/README.md) | Saliency, attribution and other explanation tools. |
| [`video-and-temporal/`](video-and-temporal/README.md) | Tracking, temporal smoothing and frame-sequence utilities (e.g. Kalman tracking for endoscopy video). |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
