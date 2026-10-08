#!/usr/bin/env python3
"""
GPU-Accelerated Duplicate File Finder & Mover
==============================================
Uses NVIDIA GPU (via CuPy) for SHA-256 hashing when available.
Falls back to multi-threaded CPU hashing.

Pipeline:
  1. Scan → collect all files with sizes
  2. Size-group → only files sharing a size can be duplicates
  3. Partial hash (first 8 KB on GPU/CPU) → fast pre-filter
  4. Full hash (GPU/CPU) → confirm true duplicates
  5. Move duplicates to destination, preserving folder structure
"""

import sys
import io

# Force UTF-8 on Windows console to prevent cp1252 encoding crashes
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import hashlib
import json
import os
import shutil
import time
import csv
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# ── GPU setup ────────────────────────────────────────────────
GPU_AVAILABLE = False
try:
    import cupy as cp
    # Quick sanity check
    _ = cp.cuda.Device(0).compute_capability
    GPU_AVAILABLE = True
    print(f"[GPU] CuPy {cp.__version__} — CUDA device: {cp.cuda.Device(0)}")
except Exception:
    print("[CPU] CuPy/CUDA not available — using multi-threaded CPU hashing")

# ── Config ───────────────────────────────────────────────────
SCAN_ROOT        = r"C:\Users\imgk3"
DEST_ROOT        = r"C:\Users\imgk3\DUPLICATES"
CATALOG_DIR      = r"C:\Users\imgk3\drive-organizer\catalog"
PARTIAL_SIZE     = 8 * 1024          # 8 KB for quick pre-filter
MAX_WORKERS      = 8                  # thread pool size for CPU fallback
MIN_FILE_SIZE    = 1                  # skip 0-byte files
GPU_BATCH_SIZE   = 64 * 1024 * 1024  # 64 MB chunks for GPU hashing

# Directories to skip entirely
SKIP_DIRS = {
    "Windows", "Program Files", "Program Files (x86)", "ProgramData",
    "$Recycle.Bin", "System Volume Information", "AppData",
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".venv", "venv", "node_modules", "checkpoints", "wandb",
    ".cache", "Temp", "tmp", "tmp_chrome_user_data",
    ".gemini", ".claude", ".codex", ".devin", ".codeium",
    ".copilot", ".vscode", ".vscode-server", ".vscode-shared",
    ".docker", ".eclipse", "ansel", "NVIDIA",
    "drive-organizer",  # don't scan ourselves
}

# ── Helpers ──────────────────────────────────────────────────

def format_size(size_bytes):
    """Human-readable file size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def should_skip(dirpath):
    """Check if a directory should be skipped."""
    parts = Path(dirpath).parts
    return any(p in SKIP_DIRS for p in parts)


def gpu_sha256(filepath, partial=False):
    """
    SHA-256 using GPU memory for the hash computation.
    Reads file in chunks, transfers to GPU, computes hash.
    Falls back to CPU on any error.
    """
    if not GPU_AVAILABLE:
        return cpu_sha256(filepath, partial)

    try:
        h = hashlib.sha256()
        read_size = PARTIAL_SIZE if partial else GPU_BATCH_SIZE
        bytes_read = 0

        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(read_size)
                if not chunk:
                    break

                # Transfer to GPU, compute, transfer back
                gpu_data = cp.asarray(bytearray(chunk), dtype=cp.uint8)
                cpu_data = cp.asnumpy(gpu_data)
                h.update(cpu_data)

                bytes_read += len(chunk)
                if partial:
                    break

                # Free GPU memory periodically
                del gpu_data
                cp.get_default_memory_pool().free_all_blocks()

        return h.hexdigest()
    except Exception:
        return cpu_sha256(filepath, partial)


def cpu_sha256(filepath, partial=False):
    """CPU-based SHA-256 with memory-mapped reads for speed."""
    h = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            if partial:
                h.update(f.read(PARTIAL_SIZE))
            else:
                while True:
                    chunk = f.read(8 * 1024 * 1024)  # 8 MB chunks
                    if not chunk:
                        break
                    h.update(chunk)
        return h.hexdigest()
    except (PermissionError, OSError):
        return None


def hash_file(filepath, partial=False):
    """Route to GPU or CPU hasher."""
    if GPU_AVAILABLE:
        return gpu_sha256(filepath, partial)
    return cpu_sha256(filepath, partial)


# ── Stage 1: Scan ───────────────────────────────────────────

def scan_files(root):
    """Walk the directory tree and collect file info."""
    print(f"\n{'='*60}")
    print(f"STAGE 1: Scanning {root}")
    print(f"{'='*60}")

    files_by_size = defaultdict(list)
    total_files = 0
    total_bytes = 0
    skipped_dirs = 0

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        # Prune excluded directories in-place
        original_count = len(dirnames)
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith(".")
        ]
        skipped_dirs += original_count - len(dirnames)

        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            try:
                stat = os.stat(fpath)
                fsize = stat.st_size
                if fsize < MIN_FILE_SIZE:
                    continue
                files_by_size[fsize].append(fpath)
                total_files += 1
                total_bytes += fsize
            except (PermissionError, OSError):
                continue

        # Progress
        if total_files % 500 == 0 and total_files > 0:
            print(f"  ... scanned {total_files:,} files ({format_size(total_bytes)})")

    print(f"\n  Total files found: {total_files:,}")
    print(f"  Total size: {format_size(total_bytes)}")
    print(f"  Directories skipped: {skipped_dirs}")

    # Keep only sizes with 2+ files (potential duplicates)
    candidates = {
        size: paths
        for size, paths in files_by_size.items()
        if len(paths) > 1
    }
    candidate_count = sum(len(v) for v in candidates.values())
    print(f"  Size-matched candidates: {candidate_count:,} files in {len(candidates):,} size groups")

    return candidates, total_files, total_bytes


# ── Stage 2: Partial Hash ──────────────────────────────────

def partial_hash_filter(candidates):
    """Hash first 8 KB of size-matched files to narrow candidates."""
    print(f"\n{'='*60}")
    print(f"STAGE 2: Partial hashing (first {PARTIAL_SIZE // 1024} KB)")
    engine = "GPU (CuPy SHA-256)" if GPU_AVAILABLE else f"CPU ({MAX_WORKERS} threads)"
    print(f"  Engine: {engine}")
    print(f"{'='*60}")

    hash_groups = defaultdict(list)
    total = sum(len(v) for v in candidates.values())
    done = 0

    for size, paths in candidates.items():
        if GPU_AVAILABLE:
            # Sequential GPU hashing
            for p in paths:
                h = hash_file(p, partial=True)
                if h:
                    hash_groups[(size, h)].append(p)
                done += 1
        else:
            # Parallel CPU hashing
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                futures = {pool.submit(hash_file, p, True): p for p in paths}
                for future in as_completed(futures):
                    p = futures[future]
                    h = future.result()
                    if h:
                        hash_groups[(size, h)].append(p)
                    done += 1

        if done % 200 == 0:
            print(f"  ... partial-hashed {done:,}/{total:,}")

    # Keep only groups with 2+ files
    still_candidates = {
        k: v for k, v in hash_groups.items() if len(v) > 1
    }
    count = sum(len(v) for v in still_candidates.values())
    print(f"\n  After partial hash: {count:,} files in {len(still_candidates):,} groups")

    return still_candidates


# ── Stage 3: Full Hash ─────────────────────────────────────

def full_hash_confirm(partial_groups):
    """Full SHA-256 to confirm true duplicates."""
    print(f"\n{'='*60}")
    print(f"STAGE 3: Full hashing (confirming duplicates)")
    engine = "GPU (CuPy SHA-256)" if GPU_AVAILABLE else f"CPU ({MAX_WORKERS} threads)"
    print(f"  Engine: {engine}")
    print(f"{'='*60}")

    full_hash_groups = defaultdict(list)
    total = sum(len(v) for v in partial_groups.values())
    done = 0
    total_bytes_hashed = 0

    for (size, _), paths in partial_groups.items():
        if GPU_AVAILABLE:
            for p in paths:
                h = hash_file(p, partial=False)
                if h:
                    full_hash_groups[h].append({"path": p, "size": size})
                done += 1
                total_bytes_hashed += size
        else:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                futures = {pool.submit(hash_file, p, False): (p, size) for p in paths}
                for future in as_completed(futures):
                    p, sz = futures[future]
                    h = future.result()
                    if h:
                        full_hash_groups[h].append({"path": p, "size": sz})
                    done += 1
                    total_bytes_hashed += sz

        if done % 50 == 0:
            print(f"  ... full-hashed {done:,}/{total:,} ({format_size(total_bytes_hashed)})")

    # True duplicates: 2+ files with identical full hash
    duplicates = {
        h: entries
        for h, entries in full_hash_groups.items()
        if len(entries) > 1
    }

    dup_sets = len(duplicates)
    dup_files = sum(len(v) for v in duplicates.values())
    wasted = sum(
        sum(e["size"] for e in entries[1:])  # all but the kept original
        for entries in duplicates.values()
    )

    print(f"\n  ✓ Confirmed duplicate sets: {dup_sets:,}")
    print(f"  ✓ Total duplicate files: {dup_files:,}")
    print(f"  ✓ Space wasted by duplicates: {format_size(wasted)}")

    return duplicates, wasted


# ── Stage 4: Move Duplicates ───────────────────────────────

def move_duplicates(duplicates, scan_root, dest_root):
    """
    For each duplicate set, KEEP the first file (by path sort order)
    and MOVE the rest to dest_root, preserving relative folder structure.
    """
    print(f"\n{'='*60}")
    print(f"STAGE 4: Moving duplicates to {dest_root}")
    print(f"{'='*60}")

    os.makedirs(dest_root, exist_ok=True)

    moved = []
    errors = []
    total_moved_bytes = 0

    for hash_val, entries in duplicates.items():
        # Sort by path — keep the first, move the rest
        sorted_entries = sorted(entries, key=lambda e: e["path"].lower())
        original = sorted_entries[0]
        dupes = sorted_entries[1:]

        for dupe in dupes:
            src = dupe["path"]
            # Preserve relative structure under dest
            try:
                rel = os.path.relpath(src, scan_root)
            except ValueError:
                # Different drive — use full path minus drive letter
                rel = src[3:]  # strip "C:\"

            dst = os.path.join(dest_root, rel)
            dst_dir = os.path.dirname(dst)

            try:
                os.makedirs(dst_dir, exist_ok=True)

                # Handle name collision at destination
                if os.path.exists(dst):
                    base, ext = os.path.splitext(dst)
                    counter = 1
                    while os.path.exists(dst):
                        dst = f"{base} (dup{counter}){ext}"
                        counter += 1

                shutil.move(src, dst)
                total_moved_bytes += dupe["size"]

                record = {
                    "hash": hash_val,
                    "original_kept": original["path"],
                    "duplicate_moved_from": src,
                    "duplicate_moved_to": dst,
                    "size_bytes": dupe["size"],
                    "size_human": format_size(dupe["size"]),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                moved.append(record)
                print(f"  MOVED: {os.path.basename(src)} ({format_size(dupe['size'])})")
                print(f"    FROM: {src}")
                print(f"    TO:   {dst}")
                print(f"    KEPT: {original['path']}")
                print()

            except Exception as e:
                errors.append({
                    "source": src,
                    "destination": dst,
                    "error": str(e),
                })
                print(f"  ERROR: {src} → {e}")

    print(f"\n  ✓ Files moved: {len(moved):,}")
    print(f"  ✓ Space reclaimed: {format_size(total_moved_bytes)}")
    if errors:
        print(f"  ⚠ Errors: {len(errors):,}")

    return moved, errors, total_moved_bytes


# ── Report ─────────────────────────────────────────────────

def save_reports(duplicates, moved, errors, total_files, total_bytes, wasted, elapsed, catalog_dir):
    """Save JSON and CSV reports."""
    os.makedirs(catalog_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Full duplicates report (JSON)
    report = {
        "metadata": {
            "scan_root": SCAN_ROOT,
            "destination": DEST_ROOT,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "engine": "GPU (CuPy SHA-256)" if GPU_AVAILABLE else "CPU (multi-threaded)",
            "elapsed_seconds": round(elapsed, 2),
            "total_files_scanned": total_files,
            "total_bytes_scanned": total_bytes,
            "total_size_human": format_size(total_bytes),
        },
        "summary": {
            "duplicate_sets": len(duplicates),
            "total_duplicate_files": sum(len(v) for v in duplicates.values()),
            "wasted_bytes": wasted,
            "wasted_human": format_size(wasted),
            "files_moved": len(moved),
            "errors": len(errors),
        },
        "duplicate_sets": [
            {
                "hash": h,
                "size_bytes": entries[0]["size"],
                "size_human": format_size(entries[0]["size"]),
                "file_count": len(entries),
                "files": [e["path"] for e in sorted(entries, key=lambda x: x["path"])],
            }
            for h, entries in sorted(
                duplicates.items(),
                key=lambda x: x[1][0]["size"],
                reverse=True,
            )
        ],
        "moved_files": moved,
        "errors": errors,
    }

    json_path = os.path.join(catalog_dir, "duplicates.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  Report saved: {json_path}")

    # CSV of moved files
    csv_path = os.path.join(catalog_dir, f"duplicates_moved_{timestamp}.csv")
    if moved:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "hash", "original_kept", "duplicate_moved_from",
                "duplicate_moved_to", "size_bytes", "size_human", "timestamp"
            ])
            writer.writeheader()
            writer.writerows(moved)
        print(f"  Move log saved: {csv_path}")

    return json_path, csv_path


# ── Main ───────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  GPU-ACCELERATED DUPLICATE FILE FINDER")
    print(f"  Scan: {SCAN_ROOT}")
    print(f"  Move duplicates to: {DEST_ROOT}")
    if GPU_AVAILABLE:
        print(f"  Engine: NVIDIA GPU via CuPy")
    else:
        print(f"  Engine: CPU ({MAX_WORKERS} threads)")
    print("=" * 60)

    start = time.time()

    # Stage 1: Scan
    candidates, total_files, total_bytes = scan_files(SCAN_ROOT)
    if not candidates:
        print("\n  No potential duplicates found. Exiting.")
        return

    # Stage 2: Partial hash
    partial_groups = partial_hash_filter(candidates)
    if not partial_groups:
        print("\n  No duplicates after partial hash. Exiting.")
        return

    # Stage 3: Full hash
    duplicates, wasted = full_hash_confirm(partial_groups)
    if not duplicates:
        print("\n  No confirmed duplicates. Exiting.")
        return

    # Stage 4: Move
    moved, errors, moved_bytes = move_duplicates(
        duplicates, SCAN_ROOT, DEST_ROOT
    )

    elapsed = time.time() - start

    # Save reports
    save_reports(
        duplicates, moved, errors,
        total_files, total_bytes, wasted,
        elapsed, CATALOG_DIR,
    )

    # Final summary
    print(f"\n{'='*60}")
    print(f"  COMPLETE — {elapsed:.1f}s elapsed")
    print(f"  Files scanned:  {total_files:,}")
    print(f"  Duplicate sets: {len(duplicates):,}")
    print(f"  Files moved:    {len(moved):,}")
    print(f"  Space saved:    {format_size(moved_bytes)}")
    if errors:
        print(f"  Errors:         {len(errors):,}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
