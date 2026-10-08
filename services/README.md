# Services

> Independently deployable backend domain services. Each owns its data and exposes a versioned contract.

| | |
|---|---|
| Path | `services/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Internal |
| Change control | Standard review; versions tagged at release |

## What belongs here

Independently deployable backend domain services. Each owns its data and exposes a versioned contract.

## What does NOT belong here

- UI code, grab-bag utilities.

## Contents

| Folder | Purpose |
|---|---|
| [`tenancy/`](tenancy/README.md) | Organisations, sites, users, roles and tenant isolation for SaaS. |
| [`billing/`](billing/README.md) | Plans, metering, invoicing, subscription lifecycle. |
| [`notifications/`](notifications/README.md) | Email, SMS, in-app and webhook notifications. |
| [`search/`](search/README.md) | Indexing and search over studies, reports and metadata. |
| [`audit-log/`](audit-log/README.md) | Append-only, tamper-evident record of who accessed or changed what. |
| [`consent/`](consent/README.md) | Patient and site consent records and enforcement of permitted data uses. |
| [`reporting/`](reporting/README.md) | Clinical and operational report generation. |
| [`integrations/`](integrations/README.md) | Adapters to external clinical systems. Translation only. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
