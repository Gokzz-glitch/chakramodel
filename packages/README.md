# Packages

> Shared libraries with no deployment of their own. One owner and a stable interface each.

| | |
|---|---|
| Path | `packages/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Internal |
| Change control | Standard review; versions tagged at release |

## What belongs here

Shared libraries with no deployment of their own. One owner and a stable interface each.

## What does NOT belong here

- Anything deployable; anything used by only one app.

## Contents

| Folder | Purpose |
|---|---|
| [`api-contracts/`](api-contracts/README.md) | Source-of-truth API schemas (OpenAPI / protobuf). Types and clients are generated from here. |
| [`domain-types/`](domain-types/README.md) | Shared domain model types (study, finding, report, ...). |
| [`ui/`](ui/README.md) | Shared design system and components. |
| [`config/`](config/README.md) | Typed configuration loading and validation. |
| [`database/`](database/README.md) | Database client, schema and migrations for product databases. Single home for migrations. |
| [`auth/`](auth/README.md) | Authentication and authorization primitives (RBAC/ABAC, tokens, sessions). |
| [`observability/`](observability/README.md) | Logging, metrics and tracing helpers with built-in PHI scrubbing. |
| [`privacy/`](privacy/README.md) | PHI detection/redaction, pseudonymisation and de-identification utilities shared by product and data pipelines. |
| [`clinical-codes/`](clinical-codes/README.md) | Terminology helpers and mapping tables (e.g. SNOMED CT, ICD, LOINC). |
| [`tooling-config/`](tooling-config/README.md) | Shared lint, format and type-check configuration. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
