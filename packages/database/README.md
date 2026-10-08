# Database

> Database client, schema and migrations for product databases. Single home for migrations.

| | |
|---|---|
| Path | `packages/database/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Internal |
| Change control | Standard review; versions tagged at release |

## What belongs here

Database client, schema and migrations for product databases. Single home for migrations.

## What does NOT belong here

- Data-warehouse or ML datasets.

## Contents

| Folder | Purpose |
|---|---|
| [`migrations/`](migrations/README.md) | Ordered, reversible schema migrations. |
| [`seeds/`](seeds/README.md) | Seed data for development - synthetic only. |
| [`fixtures/`](fixtures/README.md) | Test fixtures - synthetic only. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
