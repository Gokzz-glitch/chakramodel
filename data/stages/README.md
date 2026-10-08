# Stages

> Definition and transformation code for each dataset stage. Data flows 00 -> 06 and each stage reads only the previous one.

| | |
|---|---|
| Path | `data/stages/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Restricted - metadata only; patient data never lives in Git |
| Change control | CONTROLLED - released dataset versions are immutable |

## What belongs here

Definition and transformation code for each dataset stage. Data flows 00 -> 06 and each stage reads only the previous one.

## What does NOT belong here

- Data files; skipping a stage.

## Contents

| Folder | Purpose |
|---|---|
| [`00-raw/`](00-raw/README.md) | Immutable write-once data exactly as received, with checksums. Here: ingestion code and rules only. |
| [`01-standardized/`](01-standardized/README.md) | Format and naming normalisation (DICOM/video to canonical layout, metadata to schema). |
| [`02-deidentified/`](02-deidentified/README.md) | PHI removal, burned-in text handling, pseudonymous IDs. First stage whose output may leave the secure zone, after verification. |
| [`03-deduplicated/`](03-deduplicated/README.md) | Exact (hash) and near-duplicate (perceptual/embedding) removal, grouped by patient and video, with duplicate reports. |
| [`04-quality-filtered/`](04-quality-filtered/README.md) | Removal or flagging of unusable data (blur, poor prep, artefacts, corrupt files) with reason codes. |
| [`05-annotated/`](05-annotated/README.md) | Clinician labels - multi-reader with adjudicated consensus. |
| [`06-curated-releases/`](06-curated-releases/README.md) | Frozen, semantically versioned dataset releases consumed by ML training. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
