# Apps

> Deployable user-facing applications. Thin shells over services/ and packages/.

| | |
|---|---|
| Path | `apps/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Internal |
| Change control | Standard review; versions tagged at release |

## What belongs here

Deployable user-facing applications. Thin shells over services/ and packages/.

## What does NOT belong here

- Business logic (services/), shared code (packages/).

## Contents

| Folder | Purpose |
|---|---|
| [`web/`](web/README.md) | Customer-facing web app for clinicians and hospital staff. |
| [`admin/`](admin/README.md) | Internal operations and support console. |
| [`clinician-viewer/`](clinician-viewer/README.md) | Medical image/video viewer with AI overlays (DICOM-aware, e.g. polyp boxes on endoscopy video). |
| [`api-gateway/`](api-gateway/README.md) | Public API edge: authentication, rate limiting, tenant routing, API versioning. |
| [`worker/`](worker/README.md) | Background and asynchronous job runners. |
| [`inference-gateway/`](inference-gateway/README.md) | Routes inference requests to the right model version and enforces tenant, consent and audit checks. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
