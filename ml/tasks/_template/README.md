# Template

> Skeleton for a new clinical task. Copy, rename, fill in.

| | |
|---|---|
| Path | `ml/tasks/_template/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Confidential |
| Change control | Free-form for experiments; CONTROLLED for anything in a released model |

## What belongs here

Skeleton for a new clinical task. Copy, rename, fill in.

## What does NOT belong here

- Real task work.

## Contents

| Folder | Purpose |
|---|---|
| [`configs/`](configs/README.md) | Training and evaluation configuration (YAML) for this task. |
| [`src/`](src/README.md) | Task-specific code: models, losses, post-processing. |
| [`evaluation/`](evaluation/README.md) | Task-specific metrics, clinical endpoints and the evaluation protocol. |
| [`model-card/`](model-card/README.md) | Model card(s): intended use, data, performance, limitations, subgroup results. |
| [`tests/`](tests/README.md) | Unit and regression tests for this task. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
