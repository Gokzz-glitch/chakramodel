# Federated

> Federated learning: server, hospital-site client, aggregation strategies, privacy, simulation.

| | |
|---|---|
| Path | `ml/federated/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Confidential |
| Change control | Free-form for experiments; CONTROLLED for anything in a released model |

## What belongs here

Federated learning: server, hospital-site client, aggregation strategies, privacy, simulation.

## What does NOT belong here

- Centralised training.

## Contents

| Folder | Purpose |
|---|---|
| [`server/`](server/README.md) | Coordinator / aggregation server. |
| [`client/`](client/README.md) | Site-side training client that ships to hospitals. |
| [`strategies/`](strategies/README.md) | Aggregation and personalisation strategies. |
| [`privacy/`](privacy/README.md) | Differential privacy, secure aggregation, privacy-budget accounting. |
| [`simulation/`](simulation/README.md) | Simulated multi-site experiments on public or synthetic data. |
| [`site-onboarding/`](site-onboarding/README.md) | Procedures, checklists and kits for adding a hospital site. |
| [`communication/`](communication/README.md) | Transport, authentication and versioning of the federated protocol. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
