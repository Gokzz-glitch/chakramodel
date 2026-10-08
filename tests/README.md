# Tests

> Cross-system tests. Unit tests live next to the code they test.

| | |
|---|---|
| Path | `tests/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Internal |
| Change control | Standard review; clinical regression suites are controlled |

## What belongs here

Cross-system tests. Unit tests live next to the code they test.

## What does NOT belong here

- Unit tests.

## Contents

| Folder | Purpose |
|---|---|
| [`e2e/`](e2e/README.md) | End-to-end user journeys. |
| [`integration/`](integration/README.md) | Multi-service integration tests. |
| [`contract/`](contract/README.md) | Consumer/provider contract tests against api-contracts. |
| [`performance/`](performance/README.md) | Load, latency and soak tests. |
| [`security/`](security/README.md) | Automated security tests and scans. |
| [`clinical-regression/`](clinical-regression/README.md) | Frozen reference cases that detect behavioural change in released models. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
