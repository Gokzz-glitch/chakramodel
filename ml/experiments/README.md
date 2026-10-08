# Experiments

> Exploration and hyperparameter work. Free-form, but reproducible.

| | |
|---|---|
| Path | `ml/experiments/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Confidential |
| Change control | Free-form for experiments; CONTROLLED for anything in a released model |

## What belongs here

Exploration and hyperparameter work. Free-form, but reproducible.

## What does NOT belong here

- Anything that ships.

## Contents

| Folder | Purpose |
|---|---|
| [`configs/`](configs/README.md) | Experiment configs. |
| [`notebooks/`](notebooks/README.md) | Exploration notebooks (outputs stripped before commit - they can leak PHI). |
| [`sweeps/`](sweeps/README.md) | Hyperparameter sweep definitions. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
