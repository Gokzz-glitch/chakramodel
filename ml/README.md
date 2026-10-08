# Ml

> Machine-learning research-to-production code. Code only - data and weights live outside Git.

| | |
|---|---|
| Path | `ml/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Confidential |
| Change control | Free-form for experiments; CONTROLLED for anything in a released model |

## What belongs here

Machine-learning research-to-production code. Code only - data and weights live outside Git.

## What does NOT belong here

- Datasets, weights, patient-derived images, secrets.

## Contents

| Folder | Purpose |
|---|---|
| [`core/`](core/README.md) | Shared ML library reused by every clinical task. |
| [`tasks/`](tasks/README.md) | One folder per clinical task (indication + modality + objective). Copy _template to start a new one. |
| [`federated/`](federated/README.md) | Federated learning: server, hospital-site client, aggregation strategies, privacy, simulation. |
| [`evaluation/`](evaluation/README.md) | Cross-task evaluation framework and reports. |
| [`experiments/`](experiments/README.md) | Exploration and hyperparameter work. Free-form, but reproducible. |
| [`pipelines/`](pipelines/README.md) | Orchestrated, reproducible train -> evaluate -> package workflows. |
| [`registry/`](registry/README.md) | Model metadata and cards. Weights live in the artefact store, not here. |
| [`serving/`](serving/README.md) | Packaging and runtime for inference. |
| [`tests/`](tests/README.md) | Cross-cutting ML tests (reproducibility, determinism, leakage checks). |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
