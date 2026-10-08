# Infra

> Infrastructure as code, organised by concern, not by tool.

| | |
|---|---|
| Path | `infra/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Confidential |
| Change control | Reviewed; production changes need approval |

## What belongs here

Infrastructure as code, organised by concern, not by tool.

## What does NOT belong here

- Application code, secrets.

## Contents

| Folder | Purpose |
|---|---|
| [`provisioning/`](provisioning/README.md) | Cloud resource definitions (networks, storage, compute, identity). |
| [`containers/`](containers/README.md) | Container image definitions and base images. |
| [`orchestration/`](orchestration/README.md) | Cluster and workload definitions. |
| [`monitoring/`](monitoring/README.md) | Dashboards, alerts, SLOs, clinical-safety monitors (drift, performance). |
| [`environments/`](environments/README.md) | Per-environment configuration. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
