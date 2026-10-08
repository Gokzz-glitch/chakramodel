#!/usr/bin/env python3
"""
scaffold.py - create the healthcare-AI monorepo folder tree with a README in
every folder and subfolder.

Usage:
    python scaffold.py [target_dir] [--name "My Company Platform"] [--dry-run] [--force]

- Never overwrites an existing README unless --force is given.
- Edit SPEC below to add/rename folders; re-run any time (idempotent).
- Format of each SPEC line:   path :: what belongs here :: what does NOT belong here
"""
import argparse
from pathlib import Path, PurePosixPath

DEFAULT_NOT_HERE = "Anything that belongs to a sibling folder. If unsure, ask the owner or write an ADR."

# (data sensitivity, change control) defaults by top-level folder
DEFAULTS = {
    ".": ("Internal", "Standard review"),
    "apps": ("Internal", "Standard review; versions tagged at release"),
    "services": ("Internal", "Standard review; versions tagged at release"),
    "packages": ("Internal", "Standard review; versions tagged at release"),
    "ml": ("Confidential", "Free-form for experiments; CONTROLLED for anything in a released model"),
    "data": ("Restricted - metadata only; patient data never lives in Git", "CONTROLLED - released dataset versions are immutable"),
    "regulatory": ("Confidential", "CONTROLLED - document-controlled, approvals required"),
    "security": ("Restricted", "CONTROLLED - no secrets, ever"),
    "infra": ("Confidential", "Reviewed; production changes need approval"),
    "deployments": ("Confidential", "CONTROLLED for validated customer environments"),
    "tools": ("Internal", "Standard review"),
    "tests": ("Internal", "Standard review; clinical regression suites are controlled"),
    "docs": ("Internal", "Standard review; ADRs are append-only"),
}

# Every clinical task folder gets these subfolders
TASK_ROOTS = [
    "ml/tasks/_template",
    "ml/tasks/colonoscopy-polyp-detection",
    "ml/tasks/colorectal-cancer-histopathology",
]
TASK_DIRS = {
    "configs": ("Training and evaluation configuration (YAML) for this task.", "Secrets, absolute paths, data."),
    "src": ("Task-specific code: models, losses, post-processing.", "Generic code other tasks could reuse (put it in ml/core)."),
    "evaluation": ("Task-specific metrics, clinical endpoints and the evaluation protocol.", "Ad-hoc plots with no written protocol."),
    "model-card": ("Model card(s): intended use, data, performance, limitations, subgroup results.", "Marketing copy."),
    "tests": ("Unit and regression tests for this task.", "Tests that need real patient data."),
}

SPEC = """
. :: Healthcare AI platform monorepo - product code, ML, data governance and regulatory records in one traceable place. :: Patient data, model weights, credentials, large binaries.

# ---------------------------------------------------------------- apps
apps :: Deployable user-facing applications. Thin shells over services/ and packages/. :: Business logic (services/), shared code (packages/).
apps/web :: Customer-facing web app for clinicians and hospital staff. :: Admin-only screens (apps/admin).
apps/admin :: Internal operations and support console. :: Customer-facing features.
apps/clinician-viewer :: Medical image/video viewer with AI overlays (DICOM-aware, e.g. polyp boxes on endoscopy video). :: Model code or inference logic.
apps/api-gateway :: Public API edge: authentication, rate limiting, tenant routing, API versioning. :: Domain logic.
apps/worker :: Background and asynchronous job runners. :: Long-lived domain state.
apps/inference-gateway :: Routes inference requests to the right model version and enforces tenant, consent and audit checks. :: Training code or model-specific code.

# ---------------------------------------------------------------- services
services :: Independently deployable backend domain services. Each owns its data and exposes a versioned contract. :: UI code, grab-bag utilities.
services/tenancy :: Organisations, sites, users, roles and tenant isolation for SaaS. :: Billing logic.
services/billing :: Plans, metering, invoicing, subscription lifecycle. :: Tenant/user management.
services/notifications :: Email, SMS, in-app and webhook notifications. :: Clinical alert logic (that is a product feature, not a transport).
services/search :: Indexing and search over studies, reports and metadata. :: Source-of-truth storage.
services/audit-log :: Append-only, tamper-evident record of who accessed or changed what. :: Application debug logging.
services/consent :: Patient and site consent records and enforcement of permitted data uses. :: Authentication.
services/reporting :: Clinical and operational report generation. :: Model inference.
services/integrations :: Adapters to external clinical systems. Translation only. :: Business rules.
services/integrations/dicom :: DICOM / DICOMweb adapters. :: Image analysis.
services/integrations/fhir :: HL7 FHIR adapters and resource mapping. :: HL7 v2 (see hl7/).
services/integrations/hl7 :: HL7 v2 message adapters. :: FHIR (see fhir/).
services/integrations/pacs-vna :: PACS / vendor-neutral archive connectors. :: Viewer UI.
services/integrations/ehr :: EHR vendor-specific connectors. :: Generic FHIR code.

# ---------------------------------------------------------------- packages
packages :: Shared libraries with no deployment of their own. One owner and a stable interface each. :: Anything deployable; anything used by only one app.
packages/api-contracts :: Source-of-truth API schemas (OpenAPI / protobuf). Types and clients are generated from here. :: Hand-written types that duplicate a schema.
packages/domain-types :: Shared domain model types (study, finding, report, ...). :: Persistence code.
packages/ui :: Shared design system and components. :: App-specific screens.
packages/config :: Typed configuration loading and validation. :: Actual config values or secrets.
packages/database :: Database client, schema and migrations for product databases. Single home for migrations. :: Data-warehouse or ML datasets.
packages/database/migrations :: Ordered, reversible schema migrations. :: Data fixes run by hand.
packages/database/seeds :: Seed data for development - synthetic only. :: Real or de-identified patient data.
packages/database/fixtures :: Test fixtures - synthetic only. :: Real or de-identified patient data.
packages/auth :: Authentication and authorization primitives (RBAC/ABAC, tokens, sessions). :: User directories.
packages/observability :: Logging, metrics and tracing helpers with built-in PHI scrubbing. :: Dashboards (infra/monitoring).
packages/privacy :: PHI detection/redaction, pseudonymisation and de-identification utilities shared by product and data pipelines. :: Policy documents (regulatory/).
packages/clinical-codes :: Terminology helpers and mapping tables (e.g. SNOMED CT, ICD, LOINC). :: Licensed terminology files that cannot be redistributed.
packages/tooling-config :: Shared lint, format and type-check configuration. :: Runtime config.

# ---------------------------------------------------------------- ml
ml :: Machine-learning research-to-production code. Code only - data and weights live outside Git. :: Datasets, weights, patient-derived images, secrets.
ml/core :: Shared ML library reused by every clinical task. :: Task-specific code.
ml/core/data-loading :: Dataset readers that consume curated releases via manifests. :: Data cleaning (data/stages).
ml/core/augmentation :: Image/video augmentation with clinically plausible transforms. :: Offline dataset modification.
ml/core/metrics :: Metrics (detection, segmentation, classification, survival) with tests. :: Task-specific endpoints.
ml/core/calibration :: Probability calibration and threshold selection tools. :: Evaluation reports.
ml/core/uncertainty :: Uncertainty estimation and out-of-distribution detection. :: Model architectures.
ml/core/explainability :: Saliency, attribution and other explanation tools. :: UI rendering.
ml/core/video-and-temporal :: Tracking, temporal smoothing and frame-sequence utilities (e.g. Kalman tracking for endoscopy video). :: Single-image logic.
ml/tasks :: One folder per clinical task (indication + modality + objective). Copy _template to start a new one. :: Cross-task code (ml/core).
ml/tasks/_template :: Skeleton for a new clinical task. Copy, rename, fill in. :: Real task work.
ml/tasks/colonoscopy-polyp-detection :: Polyp detection (and tracking) in colonoscopy video. :: Histopathology work.
ml/tasks/colorectal-cancer-histopathology :: Colorectal cancer analysis on histopathology slides. :: Endoscopy work.
ml/federated :: Federated learning: server, hospital-site client, aggregation strategies, privacy, simulation. :: Centralised training.
ml/federated/server :: Coordinator / aggregation server. :: Site-side code.
ml/federated/client :: Site-side training client that ships to hospitals. :: Server logic.
ml/federated/strategies :: Aggregation and personalisation strategies. :: Transport code.
ml/federated/privacy :: Differential privacy, secure aggregation, privacy-budget accounting. :: Generic PHI redaction (packages/privacy).
ml/federated/simulation :: Simulated multi-site experiments on public or synthetic data. :: Real site data.
ml/federated/site-onboarding :: Procedures, checklists and kits for adding a hospital site. :: Signed agreements (regulatory/).
ml/federated/communication :: Transport, authentication and versioning of the federated protocol. :: Training logic.
ml/evaluation :: Cross-task evaluation framework and reports. :: Task-specific endpoints (ml/tasks/*/evaluation).
ml/evaluation/benchmarks :: Standard benchmark definitions and runners. :: Results (reports/).
ml/evaluation/subgroup-fairness :: Performance by site, device, age, sex, ethnicity and other subgroups. :: Aggregate-only metrics.
ml/evaluation/robustness-and-shift :: Robustness to scanner/device shift, artefacts, compression, noise. :: Training-time augmentation.
ml/evaluation/external-validation :: Protocols and runners for held-out external sites. :: Training data.
ml/evaluation/reports :: Generated evaluation reports linked to model and dataset versions. :: Raw predictions on patient data.
ml/experiments :: Exploration and hyperparameter work. Free-form, but reproducible. :: Anything that ships.
ml/experiments/configs :: Experiment configs. :: Task configs meant for release.
ml/experiments/notebooks :: Exploration notebooks (outputs stripped before commit - they can leak PHI). :: Production logic.
ml/experiments/sweeps :: Hyperparameter sweep definitions. :: Sweep results with patient data.
ml/pipelines :: Orchestrated, reproducible train -> evaluate -> package workflows. :: One-off scripts.
ml/registry :: Model metadata and cards. Weights live in the artefact store, not here. :: Model weights.
ml/registry/model-cards :: Published model cards per released model version. :: Draft notes.
ml/registry/release-manifests :: Per-release manifest: model hash, dataset version, code commit, metrics. :: Binary artefacts.
ml/serving :: Packaging and runtime for inference. :: Training code.
ml/serving/export :: Export to portable formats (e.g. ONNX) with parity tests. :: Training.
ml/serving/runtime :: Inference runtime used by services and edge devices. :: Gateway routing.
ml/serving/edge-optimization :: Quantisation, pruning and device-specific tuning. :: Server-only optimisation.
ml/serving/benchmarks :: Latency, throughput and memory benchmarks per target hardware. :: Accuracy evaluation.
ml/tests :: Cross-cutting ML tests (reproducibility, determinism, leakage checks). :: Task-specific tests.

# ---------------------------------------------------------------- data
data :: Data governance layer: catalogue, schemas, stage definitions, manifests, lineage and splits. Metadata only - the data itself lives in access-controlled storage. :: Patient data, images, videos, DICOM, CSV extracts.
data/catalog :: Dataset registry: one record per dataset (source, owner, DUA/licence, consent scope, modality, current version). :: Data files.
data/schemas :: Formal schemas for every stage and annotation format. :: Example data containing real values.
data/stages :: Definition and transformation code for each dataset stage. Data flows 00 -> 06 and each stage reads only the previous one. :: Data files; skipping a stage.
data/stages/00-raw :: Immutable write-once data exactly as received, with checksums. Here: ingestion code and rules only. :: Edits of any kind to raw data.
data/stages/01-standardized :: Format and naming normalisation (DICOM/video to canonical layout, metadata to schema). :: Content changes.
data/stages/02-deidentified :: PHI removal, burned-in text handling, pseudonymous IDs. First stage whose output may leave the secure zone, after verification. :: Re-identification keys.
data/stages/03-deduplicated :: Exact (hash) and near-duplicate (perceptual/embedding) removal, grouped by patient and video, with duplicate reports. :: Quality filtering.
data/stages/04-quality-filtered :: Removal or flagging of unusable data (blur, poor prep, artefacts, corrupt files) with reason codes. :: Labelling.
data/stages/05-annotated :: Clinician labels - multi-reader with adjudicated consensus. :: Unreviewed single-reader labels presented as truth.
data/stages/06-curated-releases :: Frozen, semantically versioned dataset releases consumed by ML training. :: Mutable data; edits to a published version.
data/manifests :: Per-version file lists with checksums and counts, enabling exact reconstruction. :: The files themselves.
data/lineage :: Records linking each release to input versions, code commit and parameters. :: Narrative documents.
data/splits :: Frozen train/validation/test/external definitions, split at patient and site level before any augmentation. :: Splits done at frame or image level.
data/annotation :: Labelling guidelines, label taxonomies, tool configs, inter-rater agreement reports. :: Labels themselves.
data/deidentification :: De-identification policy, rule sets and residual-PHI audit procedures. :: Identifiable data or mapping tables.
data/quality :: Validation rules (expectations) and QC reports. :: Pipeline code (data/stages).
data/access-governance :: Pointers to data-use agreements, ethics approvals and access-request process. :: Signed originals containing personal data.
data/external-datasets :: Registry entries and licences for public or third-party datasets. :: Downloaded dataset files.
data/synthetic :: Generators and tiny samples of synthetic data for tests and demos. :: Real or de-identified data.

# ---------------------------------------------------------------- regulatory
regulatory :: Quality-system and regulatory evidence (the design history of every product). Written as you build, not before submission. :: Source code, secrets.
regulatory/intended-use :: Intended use, indications for use, user and patient populations per product. :: Marketing claims.
regulatory/risk-management :: Hazard analysis and risk files, including AI-specific risks. :: Security threat models (security/).
regulatory/requirements-and-traceability :: User needs -> requirements -> design -> tests traceability matrix. :: Informal wish lists.
regulatory/software-lifecycle :: Development plans, software safety classification, third-party (SOUP/OTS) inventory. :: Code.
regulatory/verification-and-validation :: V&V protocols and reports. :: Exploratory test notes.
regulatory/clinical-evaluation :: Study protocols, ethics approvals, performance studies, literature reviews. :: Raw study data.
regulatory/ai-governance :: Model change control (including change-control plans), bias assessments, transparency and human-oversight documentation. :: Model code.
regulatory/quality-system :: SOPs, training records, internal audits, CAPA, supplier management. :: Project-management chatter.
regulatory/privacy-and-data-protection :: DPIAs, records of processing, jurisdiction notes (HIPAA, GDPR, India DPDP Act, etc.). :: Personal data.
regulatory/submissions :: Submission packages per authority. :: Drafts with no owner.
regulatory/submissions/fda :: US FDA submissions and correspondence. :: Other authorities.
regulatory/submissions/eu-mdr-ai-act :: EU MDR / AI Act technical documentation and notified-body correspondence. :: Other authorities.
regulatory/submissions/cdsco :: India CDSCO submissions and correspondence. :: Other authorities.
regulatory/submissions/other-jurisdictions :: Any other country. Create one subfolder per authority. :: Authorities that have their own folder.
regulatory/post-market :: Surveillance, complaints, vigilance reporting and performance monitoring plans. :: Support tickets without regulatory relevance.
regulatory/release-records :: Signed release record per release tying product version + model version + dataset version together. :: Unsigned drafts.

# ---------------------------------------------------------------- security
security :: Security engineering artefacts. Never any secrets. :: Credentials, keys, tokens.
security/threat-models :: Threat models per product and per data flow. :: Clinical risk files (regulatory/risk-management).
security/policies :: Security and access-control policies. :: Procedures (regulatory/quality-system).
security/penetration-tests :: Scope, reports and remediation tracking. :: Exploit code.
security/sbom-and-dependencies :: SBOMs, dependency and licence audits. :: Lockfiles (kept next to the code).
security/incident-response :: Playbooks and post-incident reviews, including breach notification. :: Live incident chatter.
security/access-reviews :: Periodic access reviews for systems and data. :: Individual personal data.

# ---------------------------------------------------------------- infra
infra :: Infrastructure as code, organised by concern, not by tool. :: Application code, secrets.
infra/provisioning :: Cloud resource definitions (networks, storage, compute, identity). :: Application config.
infra/containers :: Container image definitions and base images. :: Orchestration manifests.
infra/orchestration :: Cluster and workload definitions. :: Image builds.
infra/monitoring :: Dashboards, alerts, SLOs, clinical-safety monitors (drift, performance). :: Application logging code.
infra/environments :: Per-environment configuration. :: Secrets.
infra/environments/development :: Development environment config. :: Production values.
infra/environments/staging :: Staging config mirroring production. :: Real patient data.
infra/environments/production :: Production config; changes need approval. :: Experiments.
infra/environments/validation :: Frozen environment used for regulated verification runs. :: Anything not under change control.

# ---------------------------------------------------------------- deployments
deployments :: Packaging for each way the product reaches customers. :: Application code.
deployments/saas-cloud :: Multi-tenant cloud SaaS release packaging. :: On-prem specifics.
deployments/on-premise-hospital :: Installable single-tenant package for hospital data centres. :: Cloud-only assumptions.
deployments/edge-appliance :: Device image and update mechanism for in-room hardware (e.g. endoscopy tower). :: Server-side packaging.
deployments/federated-site-kit :: Kit installed at federated-learning sites. :: Central server packaging.
deployments/air-gapped :: Offline install and update bundles. :: Anything needing internet at runtime.

# ---------------------------------------------------------------- tools
tools :: Developer and release tooling (replaces a loose scripts/ folder). Every tool has a README and a --help. :: Product code, one-off personal scripts.
tools/setup :: Bootstrapping a new developer machine or environment. :: Daily-use tools.
tools/development :: Day-to-day helpers (lint, format, run, seed). :: Release steps.
tools/data-tools :: CLI tools for dataset inspection, hashing, manifest generation, audits. :: Stage transformation code (data/stages).
tools/release :: Versioning, changelog, release packaging and signing. :: Deployment definitions.
tools/codegen :: Code generation from api-contracts and schemas. :: Hand-written code.

# ---------------------------------------------------------------- tests
tests :: Cross-system tests. Unit tests live next to the code they test. :: Unit tests.
tests/e2e :: End-to-end user journeys. :: Component tests.
tests/integration :: Multi-service integration tests. :: Browser tests.
tests/contract :: Consumer/provider contract tests against api-contracts. :: Load tests.
tests/performance :: Load, latency and soak tests. :: Functional tests.
tests/security :: Automated security tests and scans. :: Pen-test reports (security/).
tests/clinical-regression :: Frozen reference cases that detect behavioural change in released models. :: Training data.

# ---------------------------------------------------------------- docs
docs :: Human-readable knowledge. Explains why, not just what. :: Regulated controlled documents (regulatory/).
docs/architecture :: System architecture, data flows, diagrams. :: Decision records (docs/adr).
docs/adr :: Architecture Decision Records. Append-only: supersede, never edit history. :: Meeting notes.
docs/api :: API reference and integration guides for customers. :: Internal-only design notes.
docs/runbooks :: Operational procedures and on-call guides. :: Policy documents.
docs/onboarding :: New engineer and new clinical-partner onboarding. :: Reference material.
docs/glossary :: Clinical and technical glossary shared by engineers and clinicians. :: Marketing language.
docs/product :: Product requirements, roadmap, user research summaries. :: Regulatory requirements (regulatory/).
docs/research :: Papers, preprints, literature notes and reproduction guides. :: Unpublished confidential results without owner approval.
"""


def parent_of(p: str) -> str:
    return "." if p != "." and "/" not in p else str(PurePosixPath(p).parent)


def pretty(name: str) -> str:
    return name.strip("_").replace("-", " ").replace("_", " ").title()


def load_spec():
    entries, order = {}, []
    for raw in SPEC.strip().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [x.strip() for x in line.split("::")]
        path, purpose = parts[0], parts[1]
        not_here = parts[2] if len(parts) > 2 and parts[2] else DEFAULT_NOT_HERE
        entries[path] = (purpose, not_here)
        order.append(path)
    for root in TASK_ROOTS:
        assert root in entries, f"task root missing from SPEC: {root}"
        for name, (purpose, not_here) in TASK_DIRS.items():
            p = f"{root}/{name}"
            entries[p] = (purpose, not_here)
            order.append(p)
    for p in entries:
        if p != "." and parent_of(p) not in entries:
            raise SystemExit(f"Missing intermediate folder in SPEC: {parent_of(p)} (needed by {p})")
    for p in entries:
        top = "." if p == "." else p.split("/")[0]
        if top not in DEFAULTS:
            raise SystemExit(f"No DEFAULTS entry for top-level folder: {top}")
    return entries, order


def render(path, entries, order, project):
    purpose, not_here = entries[path]
    top = "." if path == "." else path.split("/")[0]
    sensitivity, change = DEFAULTS[top]
    title = project if path == "." else pretty(path.split("/")[-1])
    kids = [c for c in order if c != "." and parent_of(c) == path]
    shown = "./" if path == "." else f"{path}/"

    out = [
        f"# {title}", "", f"> {purpose}", "",
        "| | |", "|---|---|",
        f"| Path | `{shown}` |",
        "| Owner | _TBD - name the team here and in CODEOWNERS_ |",
        f"| Data sensitivity | {sensitivity} |",
        f"| Change control | {change} |",
        "", "## What belongs here", "", purpose, "",
        "## What does NOT belong here", "", f"- {not_here}", "",
        "## Contents", "",
    ]
    if kids:
        out += ["| Folder | Purpose |", "|---|---|"]
        for c in kids:
            name = c.split("/")[-1]
            out.append(f"| [`{name}/`]({name}/README.md) | {entries[c][0]} |")
    else:
        out.append("_Leaf folder - add an index of important files as they appear._")
    out += [
        "", "## Conventions", "",
        "_Document naming, file formats and the how-to for this folder. "
        "Keep this README current: changing what the folder is for means changing this file._",
    ]
    if path != ".":
        out += ["", "## Related", "", "- Parent: [`..`](../README.md)"]
    return "\n".join(out) + "\n"


GITIGNORE = """\
# --- Never commit patient data or derived imaging ---
*.dcm
*.dicom
*.nii
*.nii.gz
*.svs
*.ndpi
*.mp4
*.avi
*.mov
*.mkv
data/stages/**/files/
# --- Model artefacts (use the artefact store + ml/registry) ---
*.pt
*.pth
*.ckpt
*.onnx
*.engine
*.tflite
*.safetensors
*.h5
*.pkl
# --- Secrets ---
.env
.env.*
!.env.example
*.pem
*.key
# --- Tooling noise ---
__pycache__/
.venv/
node_modules/
dist/
build/
.ipynb_checkpoints/
.DS_Store
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?", default="medai-platform")
    ap.add_argument("--name", default="MedAI Platform", help="project name used in the root README")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="overwrite existing READMEs")
    args = ap.parse_args()

    entries, order = load_spec()
    root = Path(args.target)
    made = skipped = 0
    for path in order:
        d = root if path == "." else root / path
        readme = d / "README.md"
        if args.dry_run:
            print(("would write " if not readme.exists() or args.force else "would keep  ") + str(readme))
            continue
        d.mkdir(parents=True, exist_ok=True)
        if readme.exists() and not args.force:
            skipped += 1
            continue
        readme.write_text(render(path, entries, order, args.name), encoding="utf-8")
        made += 1

    if not args.dry_run:
        # .github: READMEs here would show up as issue templates, so only keep placeholders
        for sub in ("workflows", "ISSUE_TEMPLATE"):
            d = root / ".github" / sub
            d.mkdir(parents=True, exist_ok=True)
            (d / ".gitkeep").touch()
        gi = root / ".gitignore"
        if not gi.exists():
            gi.write_text(GITIGNORE, encoding="utf-8")
        print(f"Folders: {len(order)} | READMEs written: {made} | kept existing: {skipped} | target: {root.resolve()}")


if __name__ == "__main__":
    main()
