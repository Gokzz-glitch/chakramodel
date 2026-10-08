# Tasks

> One folder per clinical task (indication + modality + objective). Copy _template to start a new one.

| | |
|---|---|
| Path | `ml/tasks/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Confidential |
| Change control | Free-form for experiments; CONTROLLED for anything in a released model |

## What belongs here

One folder per clinical task (indication + modality + objective). Copy _template to start a new one.

## What does NOT belong here

- Cross-task code (ml/core).

## Contents

| Folder | Purpose |
|---|---|
| [`_template/`](_template/README.md) | Skeleton for a new clinical task. Copy, rename, fill in. |
| [`colonoscopy-polyp-detection/`](colonoscopy-polyp-detection/README.md) | Polyp detection (and tracking) in colonoscopy video. |
| [`colorectal-cancer-histopathology/`](colorectal-cancer-histopathology/README.md) | Colorectal cancer analysis on histopathology slides. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
