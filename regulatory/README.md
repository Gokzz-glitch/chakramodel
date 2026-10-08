# Regulatory

> Quality-system and regulatory evidence (the design history of every product). Written as you build, not before submission.

| | |
|---|---|
| Path | `regulatory/` |
| Owner | _TBD - name the team here and in CODEOWNERS_ |
| Data sensitivity | Confidential |
| Change control | CONTROLLED - document-controlled, approvals required |

## What belongs here

Quality-system and regulatory evidence (the design history of every product). Written as you build, not before submission.

## What does NOT belong here

- Source code, secrets.

## Contents

| Folder | Purpose |
|---|---|
| [`intended-use/`](intended-use/README.md) | Intended use, indications for use, user and patient populations per product. |
| [`risk-management/`](risk-management/README.md) | Hazard analysis and risk files, including AI-specific risks. |
| [`requirements-and-traceability/`](requirements-and-traceability/README.md) | User needs -> requirements -> design -> tests traceability matrix. |
| [`software-lifecycle/`](software-lifecycle/README.md) | Development plans, software safety classification, third-party (SOUP/OTS) inventory. |
| [`verification-and-validation/`](verification-and-validation/README.md) | V&V protocols and reports. |
| [`clinical-evaluation/`](clinical-evaluation/README.md) | Study protocols, ethics approvals, performance studies, literature reviews. |
| [`ai-governance/`](ai-governance/README.md) | Model change control (including change-control plans), bias assessments, transparency and human-oversight documentation. |
| [`quality-system/`](quality-system/README.md) | SOPs, training records, internal audits, CAPA, supplier management. |
| [`privacy-and-data-protection/`](privacy-and-data-protection/README.md) | DPIAs, records of processing, jurisdiction notes (HIPAA, GDPR, India DPDP Act, etc.). |
| [`submissions/`](submissions/README.md) | Submission packages per authority. |
| [`post-market/`](post-market/README.md) | Surveillance, complaints, vigilance reporting and performance monitoring plans. |
| [`release-records/`](release-records/README.md) | Signed release record per release tying product version + model version + dataset version together. |

## Conventions

_Document naming, file formats and the how-to for this folder. Keep this README current: changing what the folder is for means changing this file._

## Related

- Parent: [`..`](../README.md)
