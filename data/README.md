# Data

> Data governance layer: catalogue, schemas, stage definitions, manifests, lineage and splits. Metadata only - the data itself lives in access-controlled storage.

| | |
|---|---|
| Path | `data/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Restricted - metadata only; patient data never lives in Git |
| Change control | CONTROLLED - released dataset versions are immutable |

## What belongs here

Data governance layer: catalogue, schemas, stage definitions, manifests, lineage and splits. Metadata only - the data itself lives in access-controlled storage.

## What does NOT belong here

- Patient data, images, videos, DICOM, CSV extracts.

## Contents

| Folder | Purpose |
|---|---|
| [`catalog/`](catalog/README.md) | Dataset registry: one record per dataset (source, owner, DUA/licence, consent scope, modality, current version). |
| [`schemas/`](schemas/README.md) | Formal schemas for every stage and annotation format. |
| [`stages/`](stages/README.md) | Definition and transformation code for each dataset stage. Data flows 00 -> 06 and each stage reads only the previous one. |
| [`manifests/`](manifests/README.md) | Per-version file lists with checksums and counts, enabling exact reconstruction. |
| [`lineage/`](lineage/README.md) | Records linking each release to input versions, code commit and parameters. |
| [`splits/`](splits/README.md) | Frozen train/validation/test/external definitions, split at patient and site level before any augmentation. |
| [`annotation/`](annotation/README.md) | Labelling guidelines, label taxonomies, tool configs, inter-rater agreement reports. |
| [`deidentification/`](deidentification/README.md) | De-identification policy, rule sets and residual-PHI audit procedures. |
| [`quality/`](quality/README.md) | Validation rules (expectations) and QC reports. |
| [`access-governance/`](access-governance/README.md) | Pointers to data-use agreements, ethics approvals and access-request process. |
| [`external-datasets/`](external-datasets/README.md) | Registry entries and licences for public or third-party datasets. |
| [`synthetic/`](synthetic/README.md) | Generators and tiny samples of synthetic data for tests and demos. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
