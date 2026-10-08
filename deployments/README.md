# Deployments

> Packaging for each way the product reaches customers.

| | |
|---|---|
| Path | `deployments/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Confidential |
| Change control | CONTROLLED for validated customer environments |

## What belongs here

Packaging for each way the product reaches customers.

## What does NOT belong here

- Application code.

## Contents

| Folder | Purpose |
|---|---|
| [`saas-cloud/`](saas-cloud/README.md) | Multi-tenant cloud SaaS release packaging. |
| [`on-premise-hospital/`](on-premise-hospital/README.md) | Installable single-tenant package for hospital data centres. |
| [`edge-appliance/`](edge-appliance/README.md) | Device image and update mechanism for in-room hardware (e.g. endoscopy tower). |
| [`federated-site-kit/`](federated-site-kit/README.md) | Kit installed at federated-learning sites. |
| [`air-gapped/`](air-gapped/README.md) | Offline install and update bundles. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
