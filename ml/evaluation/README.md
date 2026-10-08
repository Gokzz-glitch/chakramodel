# Evaluation

> Cross-task evaluation framework and reports.

| | |
|---|---|
| Path | `ml/evaluation/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Confidential |
| Change control | Free-form for experiments; CONTROLLED for anything in a released model |

## What belongs here

Cross-task evaluation framework and reports.

## What does NOT belong here

- Task-specific endpoints (ml/tasks/*/evaluation).

## Contents

| Folder | Purpose |
|---|---|
| [`benchmarks/`](benchmarks/README.md) | Standard benchmark definitions and runners. |
| [`subgroup-fairness/`](subgroup-fairness/README.md) | Performance by site, device, age, sex, ethnicity and other subgroups. |
| [`robustness-and-shift/`](robustness-and-shift/README.md) | Robustness to scanner/device shift, artefacts, compression, noise. |
| [`external-validation/`](external-validation/README.md) | Protocols and runners for held-out external sites. |
| [`reports/`](reports/README.md) | Generated evaluation reports linked to model and dataset versions. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
