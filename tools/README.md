# Tools

> Developer and release tooling (replaces a loose scripts/ folder). Every tool has a README and a --help.

| | |
|---|---|
| Path | `tools/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Internal |
| Change control | Standard review |

## What belongs here

Developer and release tooling (replaces a loose scripts/ folder). Every tool has a README and a --help.

## What does NOT belong here

- Product code, one-off personal scripts.

## Contents

| Folder | Purpose |
|---|---|
| [`setup/`](setup/README.md) | Bootstrapping a new developer machine or environment. |
| [`development/`](development/README.md) | Day-to-day helpers (lint, format, run, seed). |
| [`data-tools/`](data-tools/README.md) | CLI tools for dataset inspection, hashing, manifest generation, audits. |
| [`release/`](release/README.md) | Versioning, changelog, release packaging and signing. |
| [`codegen/`](codegen/README.md) | Code generation from api-contracts and schemas. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
