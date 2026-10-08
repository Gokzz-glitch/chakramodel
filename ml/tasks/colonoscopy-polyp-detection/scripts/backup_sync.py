#!/usr/bin/env python3
"""
ChakraModel Backup Synchronization, Recovery & Daily Scheduling System
Author: ChakraModel Engineering Team / worker_m2_g15
Date: 2026-09-16

Production-grade synchronization engine providing:
1. Target Directories Verification and Auto-Fix:
   - Verifies source (default: M:\\chakramodel) against 5 target directories.
   - Zero-tolerance chunked streaming SHA-256 (1MB buffer) for O(1) memory footprint.
   - Fast-path size mismatch pre-check (O(1)) before hashing.
   - Auto-fix for missing and corrupted files with atomic write replacement (.tmp_autofix -> atomic rename).
   - Role-based safety gates preventing corruption of audit deliverables or sibling projects.
   - Default exclusions: .venv, __pycache__, .pytest_cache, .agents, .claude, .bmad-loop, etc.
2. Downloads Directory Recovery:
   - Scans C:\\Users\\imgk3\\Downloads and J:\\My Drive\\downloads.
   - Enforces strict Tier 1 Privacy Deny-Filter (passports, resumes, leads, personal identity).
   - Validates zip integrity via testzip() and blocks 49-byte stub overwrites.
   - Recovers identified ChakraModel weights, notebooks, and metrics to designated paths.
3. Scheduled Daily Startup Execution:
   - --startup-task: enforces 06:00-11:00 AM local time window (clean exit code 0 if outside).
   - Daily execution guard in logs/backup_sync_state.json prevents duplicate multi-boot runs.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import logging
import os
import re
import shutil
import stat
import sys
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Default Constants & Paths
# ---------------------------------------------------------------------------
DEFAULT_WINDOW_START = "06:00"
DEFAULT_WINDOW_END = "11:00"
DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MB chunk buffer for streaming SHA-256

DEFAULT_SOURCE_DIR = Path("M:/chakramodel")

DEFAULT_TARGET_DIRS = [
    r"D:\15-0926chakramodel versioncontrol\chakramodel",
    r"I:\My Drive\chakramodel & pro (16-9-26_)",
    r"M:\chakramodel_audit",
    r"M:\chakramodel_backup_INCOMPLETE_DO_NOT_USE_20260909",
    r"M:\chakramodelpro",
]

DEFAULT_DOWNLOADS_DIRS = [
    Path(r"C:\Users\imgk3\Downloads"),
    Path(r"J:\My Drive\downloads"),
]

DEFAULT_LOG_FILE = DEFAULT_SOURCE_DIR / "logs" / "backup_sync.log"
DEFAULT_STATE_FILE = DEFAULT_SOURCE_DIR / "logs" / "backup_sync_state.json"
DEFAULT_LEDGER_FILE = DEFAULT_SOURCE_DIR / "logs" / "recovery_ledger.json"

DEFAULT_EXCLUDE_DIRS = {
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".agents",
    ".claude",
    ".bmad-loop",
    "_bmad-output",
    ".git",
}

DEFAULT_EXCLUDE_EXTS = {
    ".pyc",
    ".pyo",
    ".tmp",
}

logger = logging.getLogger("backup_sync")


# ---------------------------------------------------------------------------
# Cryptographic Streaming SHA-256 Engine
# ---------------------------------------------------------------------------

def stream_sha256(filepath: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    """
    Calculate the SHA-256 hexadecimal digest of a file using chunked streaming.
    Guarantees bounded RAM consumption (< 25 MB) regardless of file size.
    """
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def atomic_write_replace(
    src_path: Path,
    tgt_path: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    dry_run: bool = False,
    max_retries: int = 3,
) -> bool:
    """
    Atomically copy src_path to tgt_path:
    1. Writes to temporary file tgt_path.with_name(f"{tgt_path.name}.tmp_autofix_{uuid}").
    2. Verifies SHA-256 checksum of temporary file matches source.
    3. Clears Windows read-only attribute if target already exists.
    4. Atomically replaces tgt_path via os.replace with exponential backoff retry.
    """
    if dry_run:
        logger.info(f"[DRY-RUN] Would copy '{src_path}' -> '{tgt_path}' (atomic replace)")
        return True

    tgt_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = tgt_path.with_name(f"{tgt_path.name}.tmp_autofix_{uuid.uuid4().hex[:8]}")

    try:
        shutil.copy2(src_path, tmp_path)

        # Verify integrity of written temporary file
        src_hash = stream_sha256(src_path, chunk_size=chunk_size)
        tmp_hash = stream_sha256(tmp_path, chunk_size=chunk_size)

        if src_hash != tmp_hash:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise ValueError(
                f"SHA-256 mismatch during atomic copy for '{src_path}'! "
                f"Source: {src_hash}, Temp: {tmp_hash}"
            )

        # Retry loop for transient locks / Windows WinError 5 / WinError 32
        last_exc: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                if tgt_path.exists():
                    try:
                        os.chmod(tgt_path, stat.S_IWRITE)
                    except OSError:
                        pass
                os.replace(tmp_path, tgt_path)
                return True
            except (PermissionError, OSError) as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (2 ** attempt))
                else:
                    raise last_exc

        return True

    except Exception as exc:
        if tmp_path.exists():
            try:
                try:
                    os.chmod(tmp_path, stat.S_IWRITE)
                except OSError:
                    pass
                tmp_path.unlink()
            except OSError:
                pass
        raise exc


# ---------------------------------------------------------------------------
# Requirement 1: Target Role Classification & Safety Gates
# ---------------------------------------------------------------------------

def classify_target(target_path: Path) -> Tuple[str, Path]:
    """
    Classify the target directory and resolve its effective synchronization root:
    - LOCAL_MIRROR: Direct replica target (e.g. D:\\15-0926chakramodel versioncontrol\\chakramodel).
    - CLOUD_CONTAINER: Multi-project Google Drive container, maps to child 'chakramodel'.
    - AUDIT_WORKSPACE: M:\\chakramodel_audit (isolated deliverable, protected from overwrite).
    - QUARANTINED_BACKUP: Defunct incomplete snapshot (protected, logged).
    - SIBLING_PROJECT: M:\\chakramodelpro (active independent sibling, protected).
    """
    target_str = str(target_path).replace("/", "\\").lower()

    if "chakramodel_audit" in target_str:
        return "AUDIT_WORKSPACE", target_path

    if "incomplete_do_not_use" in target_str:
        return "QUARANTINED_BACKUP", target_path

    if target_str.endswith("chakramodelpro") or "\\chakramodelpro" in target_str and "chakramodel & pro" not in target_str:
        return "SIBLING_PROJECT", target_path

    if "chakramodel & pro" in target_str:
        # Multi-project container folder on Google Drive
        child_mirror = target_path / "chakramodel"
        return "CLOUD_CONTAINER", child_mirror

    return "LOCAL_MIRROR", target_path


def verify_and_sync_target(
    source_root: Path,
    target_path: Path,
    exclude_dirs: Set[str],
    exclude_exts: Set[str],
    dry_run: bool = False,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    force_hash: bool = False,
) -> Dict[str, Any]:
    """
    Verifies a single target directory against source_root and auto-fixes any discrepancies.
    Respects role classification safety gates.
    """
    role, effective_target = classify_target(target_path)

    stats: Dict[str, Any] = {
        "target_path": str(target_path),
        "effective_target": str(effective_target),
        "role": role,
        "status": "COMPLETED",
        "files_checked": 0,
        "files_verified_ok": 0,
        "files_missing_fixed": 0,
        "files_corrupted_fixed": 0,
        "errors": [],
    }

    # Role Safety Gates
    if role == "AUDIT_WORKSPACE":
        logger.info(f"[TARGET GATE] '{target_path}' is an AUDIT_WORKSPACE. Preserving audit reports and skipping mirror sync.")
        # Verify deliverable presence
        audit_file = target_path / "FULL_AUDIT_REPORT.md"
        if audit_file.exists():
            logger.info(f"  Verified audit deliverable present: {audit_file}")
            stats["files_verified_ok"] = 1
        return stats

    if role == "QUARANTINED_BACKUP":
        logger.warning(f"[TARGET GATE] '{target_path}' is marked as QUARANTINED_BACKUP (incomplete snapshot). Skipping sync.")
        return stats

    if role == "SIBLING_PROJECT":
        logger.info(f"[TARGET GATE] '{target_path}' is an active SIBLING_PROJECT (ChakraModel Pro). Skipping mirror sync.")
        return stats

    # Active Mirror Targets: LOCAL_MIRROR or CLOUD_CONTAINER
    logger.info(f"Synchronizing source '{source_root}' -> target mirror '{effective_target}' (Role: {role})...")

    if not source_root.exists():
        err_msg = f"Source directory does not exist: {source_root}"
        logger.error(err_msg)
        stats["status"] = "FAILED"
        stats["errors"].append(err_msg)
        return stats

    if not dry_run:
        effective_target.mkdir(parents=True, exist_ok=True)

    # Walk source tree
    for root, dirs, files in os.walk(source_root):
        # Exclude directories in-place
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".tmp_autofix")]

        rel_dir = Path(root).relative_to(source_root)

        for filename in files:
            # Skip excluded extensions or temporary files
            file_ext = Path(filename).suffix.lower()
            if file_ext in exclude_exts or filename.startswith(".tmp_autofix") or ".bak_" in filename:
                continue

            src_file = Path(root) / filename
            rel_file = rel_dir / filename
            tgt_file = effective_target / rel_file

            stats["files_checked"] += 1

            try:
                # 1. Check if target exists
                if not tgt_file.exists():
                    logger.debug(f"[MISSING] Target missing: '{rel_file}'. Auto-fixing from source...")
                    atomic_write_replace(src_file, tgt_file, chunk_size=chunk_size, dry_run=dry_run)
                    stats["files_missing_fixed"] += 1
                    continue

                # 2. Fast-path size check (O(1))
                src_size = src_file.stat().st_size
                tgt_size = tgt_file.stat().st_size

                if src_size != tgt_size:
                    logger.debug(
                        f"[CORRUPTED SIZE] '{rel_file}' size mismatch (Source: {src_size} B, Target: {tgt_size} B). Auto-fixing..."
                    )
                    atomic_write_replace(src_file, tgt_file, chunk_size=chunk_size, dry_run=dry_run)
                    stats["files_corrupted_fixed"] += 1
                    continue

                # Dry-run I/O optimization: avoid reading gigabytes of data if size matches
                if dry_run and not force_hash and src_size > 50 * 1024 * 1024:
                    logger.debug(
                        f"[DRY-RUN OPTIMIZATION] '{rel_file}' ({src_size} B) size matches; skipping multi-megabyte/gigabyte hash."
                    )
                    stats["files_verified_ok"] += 1
                    continue

                # 3. Cryptographic SHA-256 check
                src_hash = stream_sha256(src_file, chunk_size=chunk_size)
                tgt_hash = stream_sha256(tgt_file, chunk_size=chunk_size)

                if src_hash != tgt_hash:
                    logger.debug(
                        f"[CORRUPTED HASH] '{rel_file}' SHA-256 mismatch! Auto-fixing from source..."
                    )
                    atomic_write_replace(src_file, tgt_file, chunk_size=chunk_size, dry_run=dry_run)
                    stats["files_corrupted_fixed"] += 1
                else:
                    stats["files_verified_ok"] += 1

                if stats["files_checked"] % 1000 == 0:
                    logger.info(
                        f"  [Progress] {stats['files_checked']} files checked "
                        f"(OK={stats['files_verified_ok']}, Missing={stats['files_missing_fixed']}, "
                        f"Corrupted={stats['files_corrupted_fixed']})..."
                    )

            except Exception as e:
                err = f"Error verifying '{rel_file}' on '{target_path}': {e}"
                logger.error(err)
                stats["errors"].append(err)

    logger.info(
        f"Target sync finished: Checked={stats['files_checked']}, "
        f"VerifiedOK={stats['files_verified_ok']}, MissingFixed={stats['files_missing_fixed']}, "
        f"CorruptedFixed={stats['files_corrupted_fixed']}, Errors={len(stats['errors'])}"
    )
    return stats


def verify_and_sync_all_targets(
    source_root: Path,
    target_dirs: List[Path],
    exclude_dirs: Set[str],
    exclude_exts: Set[str],
    dry_run: bool = False,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    force_hash: bool = False,
) -> List[Dict[str, Any]]:
    """Verify and auto-fix across all specified target directories."""
    results = []
    for tgt in target_dirs:
        logger.info("-" * 50)
        logger.info(f"Processing Target: {tgt}")
        res = verify_and_sync_target(
            source_root=source_root,
            target_path=tgt,
            exclude_dirs=exclude_dirs,
            exclude_exts=exclude_exts,
            dry_run=dry_run,
            chunk_size=chunk_size,
            force_hash=force_hash,
        )
        results.append(res)
    return results


# ---------------------------------------------------------------------------
# Requirement 2: Downloads Directory Recovery Engine
# ---------------------------------------------------------------------------

# Tier 1: Privacy Deny-Filter Regex Patterns
PERSONAL_DENY_REGEX = re.compile(
    r"(passport|resume|curriculum[\s_\-]*vitae|\bcv\b|profile\.pdf$|tax|itr|bank|statement|"
    r"salary|payslip|pay[\s_\-]*slip|medical|prescription|aadhaar|pan|ssn|"
    r"license|id[\s_\-]*card|voter|offer[\s_\-]*letter|appraisal|contract|"
    r"confidential|private|secret|budget|lor[\-_]nit|receipt|payment|booking|"
    r"mess[\s_\-]*fees?|bill|\.ics$|leads?|corporate_leads|researcher_leads|"
    r"russia_moscow|priority_\d+.*\.csv$|\.(exe|msi|bat)$|eclipse|"
    r"acer\s*care|chatgpt\s*installer|chromesetup|desktop\.ini$|screenshot|opus_keyword)",
    re.IGNORECASE,
)

# Tier 2: ChakraModel Inclusion Keywords
CHAKRA_INDICATORS = [
    "chakra", "polyp", "kvasir", "cvc", "etis", "pranet", "colondb",
    "bytetrack", "sam2", "conformal", "anti_fabrication", "combocld",
    "om-krish", "om-final", "finalmuruga", "crossvali", "cross_dataset",
    "v7verifiactiob", "claudev7", "yolo", "combo", "fcbformer", "endoslam",
    "chakramodel_om_4", "muruga-perumal", "testingnamashivaya", "prrof",
    "mock_weights", "weights", "model_output",
]


def is_personal_or_denied(filepath: Path) -> bool:
    """Check if the filename or directory path matches any privacy deny pattern."""
    path_str = str(filepath)
    name_str = filepath.name
    return bool(PERSONAL_DENY_REGEX.search(name_str) or PERSONAL_DENY_REGEX.search(path_str))


def is_chakramodel_asset(filepath: Path) -> bool:
    """Evaluate whether a non-denied file belongs to ChakraModel."""
    name_lower = filepath.name.lower()
    path_lower = str(filepath).lower()
    ext = filepath.suffix.lower()

    # Skip raw dataset image frames and annotation label text dumps
    if ext in (".jpg", ".jpeg", ".png", ".bmp", ".gif"):
        return False
    if ext == ".txt" and not any(k in name_lower for k in ("chakra", "audit", "readme", "finding", "param", "requirement")):
        return False

    # Match ChakraModel indicators in filename itself
    if any(ind in name_lower for ind in CHAKRA_INDICATORS):
        return True

    # If checking parent folder, only match if the parent directory is explicitly
    # a known repository subtree (e.g. CHAKRAMODEL_OM_4 or chakramodel),
    # NOT just because a generic word like 'weights' or 'data' is in the path.
    is_known_repo_subtree = any(
        sub in path_lower for sub in ("chakramodel_om_4", "chakramodel")
    )
    if is_known_repo_subtree:
        # Non-model files (.pdf, .csv, .xlsx) require ChakraModel indicator in filename
        if ext not in (".pdf", ".csv", ".xlsx"):
            return True

    # Generic Kaggle kernels
    if ext == ".ipynb":
        if re.match(r"^notebook[0-9a-f]{10}", name_lower) or "finalrun" in name_lower or "testing" in name_lower:
            return True

    # Checkpoints without explicit 'chakra' in name but in weights context
    if ext in (".pth", ".pt", ".ckpt", ".onnx", ".weights"):
        if "best" in name_lower or "model" in name_lower or "yolo" in name_lower:
            return True

    return False


def resolve_recovery_destination(filepath: Path, model_root: Path) -> Tuple[str, Optional[Path]]:
    """
    Determine the category and target destination inside model_root for a recovered file.
    Generic non-model files (.pdf, .csv) require a ChakraModel indicator in their filename.
    """
    name = filepath.name
    name_lower = name.lower()
    ext = filepath.suffix.lower()

    # 1. Weights & Checkpoints
    if "mock_weights" in name_lower or name_lower == "mock_weights.zip":
        return "WEIGHTS_MOCK", model_root / "weights" / name

    if ext in (".pth", ".pt", ".ckpt", ".onnx", ".weights") or name_lower in ("om-finalkaggle-upload", "chakra_transformer_best.zip"):
        if "yolo" in name_lower or name_lower.startswith("best.pt"):
            return "WEIGHTS_YOLO", model_root / "weights" / "yolo" / name
        elif "weight" in name_lower and ext == ".zip":
            return "WEIGHTS_ARCHIVE", model_root / "weights" / name
        else:
            return "WEIGHTS_CHECKPOINT", model_root / "weights" / "checkpoints" / name

    # 2. Jupyter Notebooks
    if ext == ".ipynb":
        if "om-krish-4-6 (2)" in name_lower:
            return "PROVENANCE_NOTEBOOK", model_root / "notebooks" / "provenance" / name
        elif "om-krish" in name_lower:
            return "TRAINING_NOTEBOOK", model_root / "notebooks" / "training_runs" / name
        elif any(k in name_lower for k in ("claudev7", "crossvali", "verified_eval", "evalharness", "universal_evaluation", "v8_corrected", "v9_eval", "verify")):
            return "EVALUATION_NOTEBOOK", model_root / "notebooks" / "evaluation" / name
        else:
            return "KAGGLE_NOTEBOOK", model_root / "notebooks" / "kaggle_archive" / name

    # 3. Archives
    if ext == ".zip":
        if "dataset" in name_lower or "cvc" in name_lower:
            return "DATASET_ARCHIVE", model_root / "data" / "archive" / name
        elif "weight" in name_lower:
            return "WEIGHTS_ARCHIVE", model_root / "weights" / "archive" / name
        else:
            return "RESULTS_ARCHIVE", model_root / "results" / "archives" / name

    # 4. Evaluation Results & Logs
    if ext in (".json", ".csv"):
        if ext == ".csv" and not any(ind in name_lower for ind in CHAKRA_INDICATORS):
            return "EXCLUDE_UNRELATED", None
        return "RESULTS_DATA", model_root / "results" / "recovered" / name

    # 5. Documents & Research Papers
    if ext == ".pdf":
        if re.match(r"^\d{2}_", name):
            return "RESEARCH_PAPER", model_root / "research_papers" / name
        elif "audit" in name_lower:
            return "AUDIT_REPORT", model_root / "docs" / "audit" / name
        elif any(ind in name_lower for ind in CHAKRA_INDICATORS):
            return "PDF_DOC", model_root / "docs" / "pdfs" / name
        else:
            return "EXCLUDE_UNRELATED", None

    if ext in (".md", ".txt"):
        if not any(ind in name_lower for ind in CHAKRA_INDICATORS) and not any(k in name_lower for k in ("audit", "readme", "finding", "param", "requirement")):
            return "EXCLUDE_UNRELATED", None
        return "DOC_TEXT", model_root / "docs" / "recovered" / name

    return "OTHER_ASSET", model_root / "recovered" / name


def classify_download_file(filepath: Path, model_root: Optional[Path] = None) -> Tuple[str, Optional[str], Optional[Path]]:
    """
    Classifies a downloaded file into:
    - ('DENY_PRIVACY', None, None) if matching personal/sensitive deny patterns.
    - ('EXCLUDE_UNRELATED', None, None) if not matching ChakraModel indicators.
    - ('CHAKRAMODEL_ASSET', category, dest_path) if valid asset for recovery.
    """
    if is_personal_or_denied(filepath):
        return "DENY_PRIVACY", None, None
    if not is_chakramodel_asset(filepath):
        return "EXCLUDE_UNRELATED", None, None
    root = model_root or DEFAULT_SOURCE_DIR
    cat, dest = resolve_recovery_destination(filepath, root)
    if dest is None or cat == "EXCLUDE_UNRELATED":
        return "EXCLUDE_UNRELATED", None, None
    return "CHAKRAMODEL_ASSET", cat, dest


def validate_archive_integrity(filepath: Path, quick_check_only: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Validate that an archive file is not corrupted.
    If quick_check_only is True, verifies zip header/central directory structure (O(1)).
    Otherwise, runs full zipfile.testzip() CRC integrity check.
    """
    try:
        if not zipfile.is_zipfile(filepath):
            return False, "Not a valid zip archive according to zipfile.is_zipfile"
        if quick_check_only:
            return True, None
        with zipfile.ZipFile(filepath, "r") as z:
            bad_member = z.testzip()
            if bad_member is not None:
                return False, f"Archive CRC check failed on member: {bad_member}"
        return True, None
    except Exception as e:
        return False, str(e)


def recover_file(
    src_file: Path,
    dest_file: Path,
    category: str,
    ledger_entries: List[Dict[str, Any]],
    dry_run: bool = False,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str:
    """
    Safely recovers src_file into dest_file:
    - Prevents 49-byte stub overwrite of valid files.
    - Rejects stub archives (< 100 bytes) unconditionally.
    - Skips already identical files without unnecessary cloud streaming.
    - Verifies archive integrity if zip.
    - Creates backup of destination if content differs.
    - Atomically replaces dest_file.
    Returns action status string.
    """
    src_size = src_file.stat().st_size
    ext = src_file.suffix.lower()
    is_archive = (
        ext in (".zip", ".tar.gz", ".tgz", ".tar")
        or src_file.name.lower().endswith(".tar.gz")
        or "mock_weights" in src_file.name.lower()
        or src_file.name == "om-finalkaggle-upload"
    )

    # 1. Check archive corruption first (truncated / bad CRC archives rejected)
    if is_archive:
        quick = dry_run or (src_size > 100 * 1024 * 1024)
        valid_zip, zip_err = validate_archive_integrity(src_file, quick_check_only=quick)
        if not valid_zip:
            logger.error(f"[CORRUPT ARCHIVE] Skipping '{src_file}': {zip_err}")
            ledger_entries.append({
                "timestamp": datetime.datetime.now().isoformat(),
                "source": str(src_file),
                "destination": str(dest_file),
                "action": "SKIPPED_CORRUPT_ARCHIVE",
                "reason": zip_err,
            })
            return "SKIPPED_CORRUPT_ARCHIVE"

    # 2. Unconditional Stub Archive Protection: if archive source is < 100 bytes
    if is_archive and src_size < 100:
        if dest_file.exists():
            dest_size = dest_file.stat().st_size
            action = "BLOCKED_STUB_OVERWRITE"
            reason = f"Archive source size {src_size}B < 100B, existing {dest_size}B"
        else:
            action = "BLOCKED_STUB"
            reason = f"Archive source size {src_size}B < 100B (stub archive rejected)"

        logger.warning(
            f"[STUB PROTECTION] {action}: source '{src_file}' ({src_size}B), "
            f"target '{dest_file}'. {reason}"
        )
        ledger_entries.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "source": str(src_file),
            "destination": str(dest_file),
            "action": action,
            "reason": reason,
        })
        return action

    # Stub Protection: if source is < 100 bytes and destination exists with >= 100 bytes
    if dest_file.exists():
        dest_size = dest_file.stat().st_size
        if src_size < 100 and dest_size >= 100:
            logger.warning(
                f"[STUB PROTECTION] Blocked overwrite: source '{src_file}' is {src_size}B stub, "
                f"existing destination '{dest_file}' is {dest_size}B."
            )
            ledger_entries.append({
                "timestamp": datetime.datetime.now().isoformat(),
                "source": str(src_file),
                "destination": str(dest_file),
                "action": "BLOCKED_STUB_OVERWRITE",
                "reason": f"Source size {src_size}B < 100B, existing {dest_size}B",
            })
            return "BLOCKED_STUB_OVERWRITE"

        # 3. Check identical content
        if src_size == dest_size:
            # For cloud mounts in dry-run with multi-gigabyte archives, match on size to avoid network freeze
            if dry_run and src_size > 500 * 1024 * 1024:
                is_ident = True
                src_hash = "size_matched_dry_run"
            else:
                src_hash = stream_sha256(src_file, chunk_size=chunk_size)
                dest_hash = stream_sha256(dest_file, chunk_size=chunk_size)
                is_ident = (src_hash == dest_hash)

            if is_ident:
                logger.debug(f"[IDENTICAL] '{src_file}' already matches '{dest_file}'. Skipping.")
                ledger_entries.append({
                    "timestamp": datetime.datetime.now().isoformat(),
                    "source": str(src_file),
                    "destination": str(dest_file),
                    "action": "SKIP_IDENTICAL",
                    "hash": src_hash,
                })
                return "SKIP_IDENTICAL"

        # Existing destination differs: create backup
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = dest_file.with_name(f"{dest_file.name}.bak_{ts}")
        if not dry_run:
            shutil.copy2(dest_file, backup_file)
            logger.info(f"[BACKUP] Created backup of existing target: '{backup_file}'")

    # Perform atomic recovery copy
    logger.info(f"[RECOVERING] ({category}) '{src_file}' -> '{dest_file}'")
    atomic_write_replace(src_file, dest_file, chunk_size=chunk_size, dry_run=dry_run)

    src_hash = stream_sha256(src_file, chunk_size=chunk_size) if not dry_run else "dry_run"
    ledger_entries.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "source": str(src_file),
        "destination": str(dest_file),
        "category": category,
        "size": src_size,
        "sha256": src_hash,
        "action": "RECOVERED",
    })
    return "RECOVERED"


def scan_and_recover_downloads(
    downloads_dirs: List[Path],
    model_root: Path,
    ledger_file: Path = DEFAULT_LEDGER_FILE,
    dry_run: bool = False,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Dict[str, Any]:
    """
    Scans download directories, applies filters, and safely recovers ChakraModel assets.
    """
    logger.info("=" * 60)
    logger.info("Starting Downloads Directory Recovery Scan...")

    stats: Dict[str, Any] = {
        "directories_scanned": 0,
        "total_files_evaluated": 0,
        "privacy_denied": 0,
        "unrelated_ignored": 0,
        "recovered": 0,
        "skipped_identical": 0,
        "skipped_corrupt": 0,
        "blocked_stubs": 0,
        "errors": [],
    }

    ledger_entries: List[Dict[str, Any]] = []

    for ddir in downloads_dirs:
        if not ddir.exists():
            logger.info(f"Downloads directory not found or unmounted: '{ddir}'. Skipping.")
            continue

        stats["directories_scanned"] += 1
        logger.info(f"Scanning downloads directory: '{ddir}'...")

        try:
            # Non-recursive or shallow walk to avoid deep nested unrelated structures
            for root, dirs, files in os.walk(ddir):
                # Ignore .git, .venv, caches, and massive loose image dataset folders
                dirs[:] = [
                    d for d in dirs
                    if d not in (
                        ".git", ".venv", "__pycache__", ".pytest_cache",
                        "images", "segmented-images", "negative", "positive",
                        "synthetic", "synth", "train", "val", "test"
                    ) and "colon_cancer_dataset" not in d.lower()
                ]

                for filename in files:
                    file_path = Path(root) / filename
                    stats["total_files_evaluated"] += 1

                    try:
                        # 1. Tier 1 Privacy Deny-Filter
                        if is_personal_or_denied(file_path):
                            stats["privacy_denied"] += 1
                            continue

                        # 2. Tier 2 ChakraModel Inclusion Filter
                        if not is_chakramodel_asset(file_path):
                            stats["unrelated_ignored"] += 1
                            continue

                        # 3. Resolve Destination
                        category, dest_file = resolve_recovery_destination(file_path, model_root)
                        if dest_file is None or category == "EXCLUDE_UNRELATED":
                            stats["unrelated_ignored"] += 1
                            continue

                        # 4. Recover File
                        action = recover_file(
                            src_file=file_path,
                            dest_file=dest_file,
                            category=category,
                            ledger_entries=ledger_entries,
                            dry_run=dry_run,
                            chunk_size=chunk_size,
                        )

                        if action == "RECOVERED":
                            stats["recovered"] += 1
                        elif action == "SKIP_IDENTICAL":
                            stats["skipped_identical"] += 1
                        elif action == "SKIPPED_CORRUPT_ARCHIVE":
                            stats["skipped_corrupt"] += 1
                        elif action in ("BLOCKED_STUB_OVERWRITE", "BLOCKED_STUB"):
                            stats["blocked_stubs"] += 1

                    except Exception as e:
                        err = f"Error evaluating '{file_path}': {e}"
                        logger.error(err)
                        stats["errors"].append(err)

        except Exception as e:
            err = f"Error scanning directory '{ddir}': {e}"
            logger.error(err)
            stats["errors"].append(err)

    # Persist recovery ledger if not dry run
    if not dry_run and ledger_entries:
        try:
            ledger_file.parent.mkdir(parents=True, exist_ok=True)
            existing_ledger = []
            if ledger_file.exists():
                try:
                    with open(ledger_file, "r", encoding="utf-8") as f:
                        existing_ledger = json.load(f)
                except Exception:
                    existing_ledger = []
            existing_ledger.extend(ledger_entries)
            with open(ledger_file, "w", encoding="utf-8") as f:
                json.dump(existing_ledger, f, indent=2)
            logger.info(f"Recovery ledger written to '{ledger_file}' ({len(ledger_entries)} new entries).")
        except Exception as e:
            logger.error(f"Failed to update recovery ledger: {e}")

    logger.info(
        f"Downloads Recovery completed: Scanned={stats['directories_scanned']}, "
        f"Evaluated={stats['total_files_evaluated']}, PrivacyBlocked={stats['privacy_denied']}, "
        f"Recovered={stats['recovered']}, IdenticalSkipped={stats['skipped_identical']}, "
        f"CorruptSkipped={stats['skipped_corrupt']}, StubsBlocked={stats['blocked_stubs']}"
    )
    return stats


# ---------------------------------------------------------------------------
# Requirement 3: Scheduled Daily Sync & Time Window Guard
# ---------------------------------------------------------------------------

def parse_time_str(time_str: str) -> datetime.time:
    """Parse 'HH:MM' or 'HH:MM:SS' string into datetime.time."""
    parts = [int(p) for p in time_str.strip().split(":")]
    if len(parts) == 2:
        return datetime.time(parts[0], parts[1], 0)
    elif len(parts) == 3:
        return datetime.time(parts[0], parts[1], parts[2])
    raise ValueError(f"Invalid time format: '{time_str}'. Expected 'HH:MM' or 'HH:MM:SS'.")


def is_within_scheduled_window(
    start_str: str = DEFAULT_WINDOW_START,
    end_str: str = DEFAULT_WINDOW_END,
    current_time: Optional[datetime.time] = None,
) -> Tuple[bool, str]:
    """
    Check if the current time falls within start_str and end_str inclusive.
    """
    start_t = parse_time_str(start_str)
    end_t = parse_time_str(end_str)
    now_t = current_time or datetime.datetime.now().time()

    if start_t <= end_t:
        in_window = start_t <= now_t <= end_t
    else:
        in_window = (now_t >= start_t or now_t <= end_t)
    now_formatted = now_t.strftime("%H:%M:%S")

    if in_window:
        msg = f"Current time ({now_formatted}) is within scheduled window ({start_str}-{end_str})."
    else:
        msg = f"Outside scheduled window ({start_str}-{end_str}), skipping. Current time: {now_formatted}."

    return in_window, msg


class SyncStateManager:
    """
    Tracks and persists daily synchronization status in JSON state file.
    Guards against redundant duplicate runs on the same calendar day.
    """

    def __init__(self, state_file: Path = DEFAULT_STATE_FILE):
        self.state_file = Path(state_file)

    def load_state(self) -> Dict[str, Any]:
        """Load state from file or return empty dictionary."""
        if not self.state_file.exists():
            return {}
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load state file '{self.state_file}': {e}. Using empty state.")
            return {}

    def has_run_successfully_today(self, reference_date: Optional[datetime.date] = None) -> Tuple[bool, Optional[str]]:
        """
        Check whether backup sync has already succeeded today.
        Returns (has_run, last_run_timestamp_or_none).
        """
        today_str = (reference_date or datetime.date.today()).isoformat()
        state = self.load_state()
        last_date = state.get("last_run_date")
        last_status = state.get("last_status")
        last_timestamp = state.get("last_run_timestamp")

        if last_date == today_str and last_status == "SUCCESS":
            return True, last_timestamp

        return False, last_timestamp

    def record_run(
        self,
        status: str,
        trigger_mode: str,
        metrics: Optional[Dict[str, Any]] = None,
        reference_dt: Optional[datetime.datetime] = None,
    ) -> None:
        """Atomically record the completion of a backup sync run."""
        now = reference_dt or datetime.datetime.now()
        state = self.load_state()

        state["last_run_timestamp"] = now.isoformat()
        state["last_run_date"] = now.date().isoformat()
        state["last_status"] = status
        state["last_trigger_mode"] = trigger_mode
        state["last_metrics"] = metrics or {}

        history = state.get("history", [])
        history.append({
            "timestamp": now.isoformat(),
            "date": now.date().isoformat(),
            "status": status,
            "trigger_mode": trigger_mode,
            "metrics": metrics or {},
        })
        state["history"] = history[-15:]

        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = self.state_file.with_name(f"{self.state_file.name}.tmp_{uuid.uuid4().hex[:8]}")
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            if self.state_file.exists():
                try:
                    os.chmod(self.state_file, stat.S_IWRITE)
                except OSError:
                    pass
            os.replace(tmp_file, self.state_file)
            logger.debug(f"Sync state saved to '{self.state_file}' (status: {status}).")
        except Exception as e:
            logger.error(f"Failed writing sync state file: {e}")
            if tmp_file.exists():
                try:
                    try:
                        os.chmod(tmp_file, stat.S_IWRITE)
                    except OSError:
                        pass
                    tmp_file.unlink()
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# CLI Argument Parsing & Execution Orchestration
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the command line argument parser."""
    parser = argparse.ArgumentParser(
        prog="backup_sync.py",
        description=(
            "ChakraModel Synchronization, Recovery & Daily Scheduling System.\n"
            "Verifies and auto-fixes backup directories using chunked SHA-256,\n"
            "recovers models and notebooks from downloads, and handles daily scheduled tasks."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    action_group = parser.add_argument_group("Action Modes")
    action_group.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Run full verification, synchronization, and downloads recovery (default behavior).",
    )
    action_group.add_argument(
        "--verify-and-sync",
        action="store_true",
        default=False,
        help="Verify all target backup directories against source and auto-fix discrepancies.",
    )
    action_group.add_argument(
        "--recover-downloads",
        action="store_true",
        default=False,
        help="Scan Downloads directories and recover ChakraModel files into repository.",
    )
    action_group.add_argument(
        "--startup-task",
        action="store_true",
        default=False,
        help="Run as scheduled startup task with 06:00-11:00 AM window check and daily guard.",
    )
    action_group.add_argument(
        "--check-window",
        "--check-time-window",
        action="store_true",
        dest="check_window",
        default=False,
        help="Check if current local time is within scheduled window (06:00-11:00 AM) and exit.",
    )

    options_group = parser.add_argument_group("Paths & Options")
    options_group.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help=f"Source repository root path. Default: '{DEFAULT_SOURCE_DIR}'.",
    )
    options_group.add_argument(
        "--target-dirs",
        nargs="+",
        default=None,
        help="Target backup directories. Defaults to the 5 standard ChakraModel backup targets.",
    )
    options_group.add_argument(
        "--downloads-dirs",
        nargs="+",
        default=None,
        help="Downloads directories to scan. Defaults to C:\\Downloads and J:\\My Drive\\downloads.",
    )
    options_group.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simulate execution without modifying files or updating state.",
    )
    options_group.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force execution even if outside time window or already succeeded today.",
    )
    options_group.add_argument(
        "--force-hash",
        action="store_true",
        default=False,
        help="Force full cryptographic SHA-256 computation in dry-run mode even for large size-matched files.",
    )
    options_group.add_argument(
        "--window-start",
        type=str,
        default=DEFAULT_WINDOW_START,
        help=f"Scheduled window start time (HH:MM). Default: '{DEFAULT_WINDOW_START}'.",
    )
    options_group.add_argument(
        "--window-end",
        type=str,
        default=DEFAULT_WINDOW_END,
        help=f"Scheduled window end time (HH:MM). Default: '{DEFAULT_WINDOW_END}'.",
    )
    options_group.add_argument(
        "--state-file",
        type=Path,
        default=None,
        help="Path to JSON state file. Default: 'logs/backup_sync_state.json'.",
    )
    options_group.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Path to log output file. Default: 'logs/backup_sync.log'.",
    )
    options_group.add_argument(
        "--ledger-file",
        type=Path,
        default=None,
        help="Path to recovery ledger JSON file. Default: 'logs/recovery_ledger.json'.",
    )
    options_group.add_argument(
        "--include-venv",
        action="store_true",
        default=False,
        help="Include .venv directory during verification & sync (default: excluded).",
    )
    options_group.add_argument(
        "--include-git",
        action="store_true",
        default=False,
        help="Include .git directory during verification & sync (default: excluded).",
    )
    options_group.add_argument(
        "--include-agents",
        action="store_true",
        default=False,
        help="Include .agents and .claude metadata directories (default: excluded).",
    )
    options_group.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Enable verbose DEBUG level logging.",
    )

    return parser


def configure_logging(log_file: Path, verbose: bool = False) -> None:
    """Configure console and file logging."""
    log_level = logging.DEBUG if verbose else logging.INFO
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_file), mode="a", encoding="utf-8")
    except Exception:
        file_handler = None

    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if file_handler:
        handlers.append(file_handler)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    for h in handlers:
        h.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers.clear()
    for h in handlers:
        root.addHandler(h)


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI execution routine."""
    parser = build_parser()
    args = parser.parse_args(argv)

    source_dir = args.source_dir.resolve()
    log_file = args.log_file or (source_dir / "logs" / "backup_sync.log")
    state_file = args.state_file or (source_dir / "logs" / "backup_sync_state.json")
    ledger_file = args.ledger_file or (source_dir / "logs" / "recovery_ledger.json")

    configure_logging(log_file, args.verbose)
    state_manager = SyncStateManager(state_file)

    logger.info("=" * 60)
    logger.info("ChakraModel Backup Synchronization & Recovery System Initialized")
    logger.info(f"Source Directory: {source_dir}")

    # 1. Standalone --check-window flag
    if args.check_window and not (args.verify_and_sync or args.recover_downloads or args.startup_task or args.all):
        in_win, win_msg = is_within_scheduled_window(args.window_start, args.window_end)
        logger.info(win_msg)
        return 0 if in_win else 1

    # 2. Scheduled Startup Task Constraints
    if args.startup_task and not args.force:
        # Time Window Check (06:00-11:00 AM)
        in_win, win_msg = is_within_scheduled_window(args.window_start, args.window_end)
        if not in_win:
            logger.info(win_msg)
            logger.info("Clean exit code 0 returned for scheduled task outside active window.")
            return 0
        logger.info(f"Startup task window validated: {win_msg}")

        # Daily Guard Check
        already_run, last_ts = state_manager.has_run_successfully_today()
        if already_run:
            logger.info(
                f"Daily sync already completed successfully today (Last Run: {last_ts}). "
                f"Skipping duplicate startup run to conserve resources. Clean exit 0."
            )
            return 0

    # 3. Determine Execution Actions
    run_all = args.all or (not args.verify_and_sync and not args.recover_downloads and not args.check_window)
    do_verify_sync = args.verify_and_sync or run_all or args.startup_task
    do_recover_downloads = args.recover_downloads or run_all or args.startup_task

    # Setup Target and Download Directories
    if args.target_dirs:
        target_dirs = [Path(t) for t in args.target_dirs]
    else:
        target_dirs = [Path(t) for t in DEFAULT_TARGET_DIRS]

    if args.downloads_dirs:
        downloads_dirs = [Path(d) for d in args.downloads_dirs]
    else:
        downloads_dirs = DEFAULT_DOWNLOADS_DIRS

    # Exclusions configuration
    exclude_dirs = set(DEFAULT_EXCLUDE_DIRS)
    if args.include_venv:
        exclude_dirs.discard(".venv")
    if args.include_git:
        exclude_dirs.discard(".git")
    if args.include_agents:
        exclude_dirs.discard(".agents")
        exclude_dirs.discard(".claude")
        exclude_dirs.discard(".bmad-loop")
        exclude_dirs.discard("_bmad-output")

    exclude_exts = set(DEFAULT_EXCLUDE_EXTS)

    trigger_mode = "startup_task" if args.startup_task else ("manual_all" if run_all else "manual_action")
    metrics: Dict[str, Any] = {
        "verify_and_sync_executed": do_verify_sync,
        "recover_downloads_executed": do_recover_downloads,
        "dry_run": args.dry_run,
        "targets_results": [],
        "recovery_stats": {},
    }

    start_time = datetime.datetime.now()
    success = True

    try:
        # A. Execute Target Directories Verification & Auto-Fix
        if do_verify_sync:
            logger.info(">>> Starting Requirement 1: Target Directories Verification & Auto-Fix...")
            tgt_results = verify_and_sync_all_targets(
                source_root=source_dir,
                target_dirs=target_dirs,
                exclude_dirs=exclude_dirs,
                exclude_exts=exclude_exts,
                dry_run=args.dry_run,
                force_hash=getattr(args, "force_hash", False),
            )
            metrics["targets_results"] = tgt_results
            for res in tgt_results:
                role = res.get("role")
                if role in ("LOCAL_MIRROR", "CLOUD_CONTAINER"):
                    if res.get("status") == "FAILED" or len(res.get("errors", [])) > 0:
                        logger.error(
                            f"Active target '{res.get('target_path')}' ({role}) reported failure/errors: "
                            f"{res.get('errors')}"
                        )
                        success = False

        # B. Execute Downloads Recovery
        if do_recover_downloads:
            logger.info(">>> Starting Requirement 2: Downloads Directory Recovery...")
            rec_stats = scan_and_recover_downloads(
                downloads_dirs=downloads_dirs,
                model_root=source_dir,
                ledger_file=ledger_file,
                dry_run=args.dry_run,
            )
            metrics["recovery_stats"] = rec_stats
            if rec_stats.get("errors") and len(rec_stats.get("errors", [])) > 0:
                logger.error(f"Downloads recovery reported errors: {rec_stats.get('errors')}")
                success = False

    except Exception as exc:
        logger.exception(f"Fatal error during backup synchronization: {exc}")
        success = False

    duration = (datetime.datetime.now() - start_time).total_seconds()
    metrics["duration_seconds"] = duration
    status = "SUCCESS" if success else "FAILED"

    # Persist state unless dry-run
    if not args.dry_run:
        state_manager.record_run(
            status=status,
            trigger_mode=trigger_mode,
            metrics=metrics,
        )

    logger.info(f"ChakraModel Backup Sync finished with status: {status} in {duration:.2f}s")
    logger.info("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
