# MedAI Platform

> Healthcare AI platform monorepo - product code, ML, data governance and regulatory records in one traceable place.

| | |
|---|---|
| Path | `./` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Internal |
| Change control | Standard review |

## What belongs here

Healthcare AI platform monorepo - product code, ML, data governance and regulatory records in one traceable place.

## What does NOT belong here

- Patient data, model weights, credentials, large binaries.

## Contents

| Folder | Purpose |
|---|---|
| [`apps/`](apps/README.md) | Deployable user-facing applications. Thin shells over services/ and packages/. |
| [`services/`](services/README.md) | Independently deployable backend domain services. Each owns its data and exposes a versioned contract. |
| [`packages/`](packages/README.md) | Shared libraries with no deployment of their own. One owner and a stable interface each. |
| [`ml/`](ml/README.md) | Machine-learning research-to-production code. Code only - data and weights live outside Git. |
| [`data/`](data/README.md) | Data governance layer: catalogue, schemas, stage definitions, manifests, lineage and splits. Metadata only - the data itself lives in access-controlled storage. |
| [`regulatory/`](regulatory/README.md) | Quality-system and regulatory evidence (the design history of every product). Written as you build, not before submission. |
| [`security/`](security/README.md) | Security engineering artefacts. Never any secrets. |
| [`infra/`](infra/README.md) | Infrastructure as code, organised by concern, not by tool. |
| [`deployments/`](deployments/README.md) | Packaging for each way the product reaches customers. |
| [`tools/`](tools/README.md) | Developer and release tooling (replaces a loose scripts/ folder). Every tool has a README and a --help. |
| [`tests/`](tests/README.md) | Cross-system tests. Unit tests live next to the code they test. |
| [`docs/`](docs/README.md) | Human-readable knowledge. Explains why, not just what. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._
