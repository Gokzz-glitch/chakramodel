# Registry

> Model metadata and cards. Weights live in the artefact store, not here.

| | |
|---|---|
| Path | `ml/registry/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Confidential |
| Change control | Free-form for experiments; CONTROLLED for anything in a released model |

## What belongs here

Model metadata and cards. Weights live in the artefact store, not here.

## What does NOT belong here

- Model weights.

## Contents

| Folder | Purpose |
|---|---|
| [`model-cards/`](model-cards/README.md) | Published model cards per released model version. |
| [`release-manifests/`](release-manifests/README.md) | Per-release manifest: model hash, dataset version, code commit, metrics. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
