# Environments

> Per-environment configuration.

| | |
|---|---|
| Path | `infra/environments/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Confidential |
| Change control | Reviewed; production changes need approval |

## What belongs here

Per-environment configuration.

## What does NOT belong here

- Secrets.

## Contents

| Folder | Purpose |
|---|---|
| [`development/`](development/README.md) | Development environment config. |
| [`staging/`](staging/README.md) | Staging config mirroring production. |
| [`production/`](production/README.md) | Production config; changes need approval. |
| [`validation/`](validation/README.md) | Frozen environment used for regulated verification runs. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
