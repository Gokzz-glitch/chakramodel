#!/usr/bin/env python3
"""
Daily Drive Duplicate Finder — GPU-Accelerated with Detailed Logging
=====================================================================
Designed to run automatically every day after boot (16 min delay).
Creates exhaustive daily changelogs in drive-organizer/logs/

Pipeline:
  1. Scan → collect all files with sizes
  2. Size-group → only files sharing a size can be duplicates
  3. Partial hash (first 8 KB) → fast pre-filter
  4. Full hash → confirm true duplicates
  5. Move NEW duplicates to C:\Users\imgk3\DUPLICATES
  6. Write detailed daily changelog
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
import logging
import platform
import socket
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── GPU setup ────────────────────────────────────────────────
GPU_AVAILABLE = False
GPU_NAME = "N/A"
try:
    import cupy as cp
    _ = cp.cuda.Device(0).compute_capability
    GPU_AVAILABLE = True
    GPU_NAME = str(cp.cuda.Device(0))
except Exception:
    pass

# ── Config ───────────────────────────────────────────────────
SCAN_ROOT        = r"C:\Users\imgk3"
DEST_ROOT        = r"C:\Users\imgk3\DUPLICATES"
TOOLKIT_DIR      = r"C:\Users\imgk3\drive-organizer"
CATALOG_DIR      = os.path.join(TOOLKIT_DIR, "catalog")
LOG_DIR          = os.path.join(TOOLKIT_DIR, "logs")
DAILY_LOG_DIR    = os.path.join(LOG_DIR, "daily")
STATE_FILE       = os.path.join(CATALOG_DIR, "known_hashes.json")
PARTIAL_SIZE     = 8 * 1024
MAX_WORKERS      = 8
MIN_FILE_SIZE    = 1
GPU_BATCH_SIZE   = 64 * 1024 * 1024

SKIP_DIRS = {
    "Windows", "Program Files", "Program Files (x86)", "ProgramData",
    "$Recycle.Bin", "System Volume Information", "AppData",
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".venv", "venv", "node_modules", "checkpoints", "wandb",
    ".cache", "Temp", "tmp", "tmp_chrome_user_data",
    ".gemini", ".claude", ".codex", ".devin", ".codeium",
    ".copilot", ".vscode", ".vscode-server", ".vscode-shared",
    ".docker", ".eclipse", "ansel", "NVIDIA",
    ".overture", ".p2", ".redhat", ".local", ".ipython",
    ".jupyter", ".matplotlib", ".antigravity-ide", ".ghcp-appmod",
    ".bmad", ".devin-shared", "drive-organizer",
}

# ── Logging Setup ────────────────────────────────────────────

def setup_logging(run_id):
    """Create detailed log file for this run."""
    os.makedirs(DAILY_LOG_DIR, exist_ok=True)

    log_file = os.path.join(DAILY_LOG_DIR, f"{run_id}.log")

    # File handler — detailed
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    # Console handler — summary
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))

    logger = logging.getLogger("DailyDuplicateFinder")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger, log_file


# ── Helpers ──────────────────────────────────────────────────

def format_size(size_bytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def gpu_sha256(filepath, partial=False):
    if not GPU_AVAILABLE:
        return cpu_sha256(filepath, partial)
    try:
        h = hashlib.sha256()
        read_size = PARTIAL_SIZE if partial else GPU_BATCH_SIZE
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(read_size)
                if not chunk:
                    break
                gpu_data = cp.asarray(bytearray(chunk), dtype=cp.uint8)
                cpu_data = cp.asnumpy(gpu_data)
                h.update(cpu_data)
                del gpu_data
                cp.get_default_memory_pool().free_all_blocks()
                if partial:
                    break
        return h.hexdigest()
    except Exception:
        return cpu_sha256(filepath, partial)


def cpu_sha256(filepath, partial=False):
    h = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            if partial:
                h.update(f.read(PARTIAL_SIZE))
            else:
                while True:
                    chunk = f.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    h.update(chunk)
        return h.hexdigest()
    except (PermissionError, OSError):
        return None


def hash_file(filepath, partial=False):
    if GPU_AVAILABLE:
        return gpu_sha256(filepath, partial)
    return cpu_sha256(filepath, partial)


def load_known_hashes():
    """Load previously seen file hashes to detect NEW duplicates only."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"files": {}, "moved_hashes": [], "last_run": None}


def save_known_state(state):
    os.makedirs(CATALOG_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ── Core Pipeline ────────────────────────────────────────────

def scan_files(root, log):
    log.info("=" * 70)
    log.info("STAGE 1: SCANNING FILES")
    log.info(f"  Root: {root}")
    log.info("=" * 70)

    files_by_size = defaultdict(list)
    all_files = []
    total_files = 0
    total_bytes = 0
    dir_count = 0
    skipped_dirs_count = 0

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        original = len(dirnames)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        skipped_dirs_count += original - len(dirnames)
        dir_count += 1

        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            try:
                stat = os.stat(fpath)
                fsize = stat.st_size
                if fsize < MIN_FILE_SIZE:
                    continue

                file_info = {
                    "path": fpath,
                    "size": fsize,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                }
                files_by_size[fsize].append(fpath)
                all_files.append(file_info)
                total_files += 1
                total_bytes += fsize
            except (PermissionError, OSError) as e:
                log.debug(f"  SKIP (permission): {fpath} — {e}")

        if total_files % 500 == 0 and total_files > 0:
            log.debug(f"  ... scanned {total_files:,} files ({format_size(total_bytes)})")

    log.info(f"  Directories traversed: {dir_count:,}")
    log.info(f"  Directories skipped:   {skipped_dirs_count:,}")
    log.info(f"  Total files found:     {total_files:,}")
    log.info(f"  Total size:            {format_size(total_bytes)}")

    candidates = {s: p for s, p in files_by_size.items() if len(p) > 1}
    candidate_count = sum(len(v) for v in candidates.values())
    log.info(f"  Size-matched candidates: {candidate_count:,} files in {len(candidates):,} groups")

    return candidates, all_files, total_files, total_bytes


def partial_hash_filter(candidates, log):
    log.info("")
    log.info("=" * 70)
    engine = "GPU (CuPy SHA-256)" if GPU_AVAILABLE else f"CPU ({MAX_WORKERS} threads)"
    log.info(f"STAGE 2: PARTIAL HASHING (first {PARTIAL_SIZE // 1024} KB) — {engine}")
    log.info("=" * 70)

    hash_groups = defaultdict(list)
    total = sum(len(v) for v in candidates.values())
    done = 0

    for size, paths in candidates.items():
        if GPU_AVAILABLE:
            for p in paths:
                h = hash_file(p, partial=True)
                if h:
                    hash_groups[(size, h)].append(p)
                done += 1
                log.debug(f"  PARTIAL HASH: {os.path.basename(p)} → {h[:16]}...")
        else:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                futures = {pool.submit(hash_file, p, True): p for p in paths}
                for future in as_completed(futures):
                    p = futures[future]
                    h = future.result()
                    if h:
                        hash_groups[(size, h)].append(p)
                    done += 1
                    log.debug(f"  PARTIAL HASH: {os.path.basename(p)} → {h[:16] if h else 'FAILED'}...")

        if done % 200 == 0 and done > 0:
            log.info(f"  ... partial-hashed {done:,}/{total:,}")

    still = {k: v for k, v in hash_groups.items() if len(v) > 1}
    count = sum(len(v) for v in still.values())
    log.info(f"  After partial hash filter: {count:,} files in {len(still):,} groups")
    return still


def full_hash_confirm(partial_groups, log):
    log.info("")
    log.info("=" * 70)
    engine = "GPU (CuPy SHA-256)" if GPU_AVAILABLE else f"CPU ({MAX_WORKERS} threads)"
    log.info(f"STAGE 3: FULL HASHING — {engine}")
    log.info("=" * 70)

    full_groups = defaultdict(list)
    total = sum(len(v) for v in partial_groups.values())
    done = 0
    bytes_hashed = 0

    for (size, _), paths in partial_groups.items():
        if GPU_AVAILABLE:
            for p in paths:
                h = hash_file(p, partial=False)
                if h:
                    full_groups[h].append({"path": p, "size": size})
                done += 1
                bytes_hashed += size
                log.debug(f"  FULL HASH: {p} ({format_size(size)}) → {h[:16]}...")
        else:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                futures = {pool.submit(hash_file, p, False): (p, size) for p in paths}
                for future in as_completed(futures):
                    p, sz = futures[future]
                    h = future.result()
                    if h:
                        full_groups[h].append({"path": p, "size": sz})
                    done += 1
                    bytes_hashed += sz
                    log.debug(f"  FULL HASH: {p} ({format_size(sz)}) → {h[:16] if h else 'FAILED'}...")

        if done % 50 == 0 and done > 0:
            log.info(f"  ... full-hashed {done:,}/{total:,} ({format_size(bytes_hashed)})")

    duplicates = {h: e for h, e in full_groups.items() if len(e) > 1}
    dup_sets = len(duplicates)
    dup_files = sum(len(v) for v in duplicates.values())
    wasted = sum(sum(e["size"] for e in entries[1:]) for entries in duplicates.values())

    log.info(f"  Confirmed duplicate sets:  {dup_sets:,}")
    log.info(f"  Total duplicate files:     {dup_files:,}")
    log.info(f"  Wasted space (duplicates): {format_size(wasted)}")

    return duplicates, wasted


def move_duplicates(duplicates, scan_root, dest_root, known_state, log):
    log.info("")
    log.info("=" * 70)
    log.info(f"STAGE 4: MOVING DUPLICATES → {dest_root}")
    log.info("=" * 70)

    # Check if J: drive is available
    if not os.path.exists(os.path.splitdrive(dest_root)[0] + "\\"):
        log.warning(f"  ⚠ Destination drive not available: {dest_root}")
        log.warning(f"  ⚠ Skipping move — duplicates will be logged but not moved")
        return [], [], 0

    os.makedirs(dest_root, exist_ok=True)

    already_moved = set(known_state.get("moved_hashes", []))
    moved = []
    errors = []
    total_moved_bytes = 0

    for hash_val, entries in duplicates.items():
        sorted_entries = sorted(entries, key=lambda e: e["path"].lower())
        original = sorted_entries[0]
        dupes = sorted_entries[1:]

        for dupe in dupes:
            src = dupe["path"]

            # Skip if already processed in a previous run
            file_key = f"{hash_val}:{src}"
            if file_key in already_moved:
                log.debug(f"  SKIP (already processed): {src}")
                continue

            try:
                rel = os.path.relpath(src, scan_root)
            except ValueError:
                rel = src[3:]

            dst = os.path.join(dest_root, rel)
            dst_dir = os.path.dirname(dst)

            try:
                os.makedirs(dst_dir, exist_ok=True)

                if os.path.exists(dst):
                    base, ext = os.path.splitext(dst)
                    counter = 1
                    while os.path.exists(dst):
                        dst = f"{base} (dup{counter}){ext}"
                        counter += 1

                file_size = dupe["size"]
                shutil.move(src, dst)
                total_moved_bytes += file_size

                record = {
                    "hash": hash_val,
                    "original_kept": original["path"],
                    "duplicate_moved_from": src,
                    "duplicate_moved_to": dst,
                    "size_bytes": file_size,
                    "size_human": format_size(file_size),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                moved.append(record)
                already_moved.add(file_key)

                log.info(f"  ✓ MOVED: {os.path.basename(src)}")
                log.info(f"      Size:     {format_size(file_size)}")
                log.info(f"      From:     {src}")
                log.info(f"      To:       {dst}")
                log.info(f"      Original: {original['path']}")
                log.info(f"      Hash:     {hash_val}")
                log.info("")

            except Exception as e:
                errors.append({"source": src, "destination": dst, "error": str(e)})
                log.error(f"  ✗ ERROR moving {src}: {e}")

    known_state["moved_hashes"] = list(already_moved)
    log.info(f"  Files moved this run:   {len(moved):,}")
    log.info(f"  Space reclaimed:        {format_size(total_moved_bytes)}")
    if errors:
        log.warning(f"  Errors:                 {len(errors):,}")

    return moved, errors, total_moved_bytes


# ── Daily Changelog ──────────────────────────────────────────

def write_daily_changelog(run_id, log_file, all_files, duplicates, moved, errors,
                          total_files, total_bytes, wasted, moved_bytes, elapsed, known_state, log):
    """Write an extremely detailed daily changelog markdown file."""
    log.info("")
    log.info("=" * 70)
    log.info("STAGE 5: WRITING DAILY CHANGELOG")
    log.info("=" * 70)

    os.makedirs(DAILY_LOG_DIR, exist_ok=True)
    changelog_path = os.path.join(DAILY_LOG_DIR, f"{run_id}_CHANGELOG.md")

    today = datetime.now()
    prev_state = known_state.get("last_run", {})
    prev_file_count = prev_state.get("total_files", 0)
    prev_total_bytes = prev_state.get("total_bytes", 0)

    lines = []
    lines.append(f"# 📋 Daily Drive Report — {today.strftime('%A, %B %d, %Y')}")
    lines.append(f"")
    lines.append(f"**Run ID:** `{run_id}`")
    lines.append(f"**Generated:** {today.strftime('%Y-%m-%d %H:%M:%S')} IST")
    lines.append(f"**Log File:** [{run_id}.log](file:///{log_file.replace(os.sep, '/')})")
    lines.append(f"**Engine:** {'GPU (CuPy SHA-256 on ' + GPU_NAME + ')' if GPU_AVAILABLE else 'CPU (multi-threaded, 8 workers)'}")
    lines.append(f"**Elapsed:** {elapsed:.1f} seconds")
    lines.append(f"")

    # System info
    lines.append(f"## 🖥️ System Information")
    lines.append(f"| Property | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Hostname | `{socket.gethostname()}` |")
    lines.append(f"| OS | `{platform.platform()}` |")
    lines.append(f"| Python | `{platform.python_version()}` |")
    lines.append(f"| GPU Available | `{GPU_AVAILABLE}` |")
    lines.append(f"| GPU | `{GPU_NAME}` |")
    lines.append(f"| Scan Root | `{SCAN_ROOT}` |")
    lines.append(f"| Destination | `{DEST_ROOT}` |")
    lines.append(f"")

    # Drive stats
    lines.append(f"## 📊 Drive Statistics")
    lines.append(f"| Metric | Today | Previous | Change |")
    lines.append(f"|---|---|---|---|")
    file_diff = total_files - prev_file_count if prev_file_count else "N/A"
    byte_diff = total_bytes - prev_total_bytes if prev_total_bytes else "N/A"
    file_diff_str = f"{file_diff:+,}" if isinstance(file_diff, int) else file_diff
    byte_diff_str = format_size(byte_diff) if isinstance(byte_diff, int) else byte_diff
    lines.append(f"| Total Files | {total_files:,} | {prev_file_count:,} | {file_diff_str} |")
    lines.append(f"| Total Size | {format_size(total_bytes)} | {format_size(prev_total_bytes)} | {byte_diff_str} |")
    lines.append(f"")

    # New files since last run
    prev_files_set = set(known_state.get("files", {}).keys())
    current_files = {f["path"]: f for f in all_files}
    new_files = [f for p, f in current_files.items() if p not in prev_files_set]
    removed_files = [p for p in prev_files_set if p not in current_files]

    if new_files or removed_files:
        lines.append(f"## 🆕 File Changes Since Last Run")
        lines.append(f"")

        if new_files:
            lines.append(f"### New Files ({len(new_files):,})")
            lines.append(f"| # | File | Size | Created | Path |")
            lines.append(f"|---|---|---|---|---|")
            for i, nf in enumerate(sorted(new_files, key=lambda x: x["size"], reverse=True)[:100], 1):
                name = os.path.basename(nf["path"])
                lines.append(f"| {i} | `{name}` | {format_size(nf['size'])} | {nf['created'][:19]} | `{nf['path']}` |")
            if len(new_files) > 100:
                lines.append(f"| ... | *{len(new_files) - 100} more files not shown* | | | |")
            lines.append(f"")

        if removed_files:
            lines.append(f"### Removed / Moved Files ({len(removed_files):,})")
            lines.append(f"| # | Path |")
            lines.append(f"|---|---|")
            for i, rp in enumerate(sorted(removed_files)[:100], 1):
                lines.append(f"| {i} | `{rp}` |")
            if len(removed_files) > 100:
                lines.append(f"| ... | *{len(removed_files) - 100} more not shown* | |")
            lines.append(f"")

    # Duplicate analysis
    lines.append(f"## 🔍 Duplicate Analysis")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Duplicate sets found | {len(duplicates):,} |")
    lines.append(f"| Total duplicate files | {sum(len(v) for v in duplicates.values()):,} |")
    lines.append(f"| Wasted space | {format_size(wasted)} |")
    lines.append(f"")

    if duplicates:
        lines.append(f"### Duplicate Sets (sorted by size, largest first)")
        lines.append(f"")
        sorted_dups = sorted(duplicates.items(), key=lambda x: x[1][0]["size"], reverse=True)
        for idx, (hash_val, entries) in enumerate(sorted_dups, 1):
            size = entries[0]["size"]
            lines.append(f"#### Set {idx} — `{format_size(size)}` × {len(entries)} copies (Hash: `{hash_val[:16]}...`)")
            lines.append(f"| # | Status | File Path |")
            lines.append(f"|---|---|---|")
            sorted_e = sorted(entries, key=lambda e: e["path"].lower())
            for j, e in enumerate(sorted_e):
                status = "✅ KEPT" if j == 0 else "🔄 MOVED"
                lines.append(f"| {j+1} | {status} | `{e['path']}` |")
            lines.append(f"")

    # Move operations
    lines.append(f"## 📦 Move Operations This Run")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Files moved | {len(moved):,} |")
    lines.append(f"| Space reclaimed | {format_size(moved_bytes)} |")
    lines.append(f"| Errors | {len(errors):,} |")
    lines.append(f"")

    if moved:
        lines.append(f"### Detailed Move Log")
        lines.append(f"| # | File | Size | From → To |")
        lines.append(f"|---|---|---|---|")
        for i, m in enumerate(moved, 1):
            name = os.path.basename(m["duplicate_moved_from"])
            lines.append(f"| {i} | `{name}` | {m['size_human']} | `{m['duplicate_moved_from']}` → `{m['duplicate_moved_to']}` |")
        lines.append(f"")

    if errors:
        lines.append(f"### ⚠️ Errors")
        lines.append(f"| # | Source | Error |")
        lines.append(f"|---|---|---|")
        for i, e in enumerate(errors, 1):
            lines.append(f"| {i} | `{e['source']}` | {e['error']} |")
        lines.append(f"")

    # Extension breakdown
    ext_stats = defaultdict(lambda: {"count": 0, "bytes": 0})
    for f in all_files:
        ext = os.path.splitext(f["path"])[1].lower() or "[none]"
        ext_stats[ext]["count"] += 1
        ext_stats[ext]["bytes"] += f["size"]

    lines.append(f"## 📁 File Type Breakdown")
    lines.append(f"| Extension | Files | Total Size | % of Files |")
    lines.append(f"|---|---|---|---|")
    for ext, stats in sorted(ext_stats.items(), key=lambda x: x[1]["bytes"], reverse=True)[:30]:
        pct = (stats["count"] / total_files * 100) if total_files else 0
        lines.append(f"| `{ext}` | {stats['count']:,} | {format_size(stats['bytes'])} | {pct:.1f}% |")
    lines.append(f"")

    # Footer
    lines.append(f"---")
    lines.append(f"*Report generated by drive-organizer Daily Duplicate Finder*")
    lines.append(f"*Next run: Tomorrow after 16 minutes post-boot*")

    with open(changelog_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    log.info(f"  Changelog saved: {changelog_path}")

    # Also maintain a running master log (append-only)
    master_log = os.path.join(LOG_DIR, "MASTER_LOG.md")
    is_new = not os.path.exists(master_log)
    with open(master_log, "a", encoding="utf-8") as f:
        if is_new:
            f.write("# 📒 Drive Organizer — Master Log\n\n")
            f.write("Cumulative log of all daily runs.\n\n")
            f.write("| Date | Run ID | Files Scanned | Duplicates Found | Files Moved | Space Reclaimed | Duration | Engine |\n")
            f.write("|---|---|---|---|---|---|---|---|\n")
        engine = "GPU" if GPU_AVAILABLE else "CPU"
        f.write(f"| {today.strftime('%Y-%m-%d')} | `{run_id}` | {total_files:,} | {len(duplicates):,} sets | {len(moved):,} | {format_size(moved_bytes)} | {elapsed:.1f}s | {engine} |\n")

    log.info(f"  Master log updated: {master_log}")

    # Update known state for next run comparison
    known_state["files"] = {f["path"]: {"size": f["size"], "modified": f["modified"]} for f in all_files}
    known_state["last_run"] = {
        "run_id": run_id,
        "timestamp": today.isoformat(),
        "total_files": total_files,
        "total_bytes": total_bytes,
        "duplicates_found": len(duplicates),
        "files_moved": len(moved),
        "bytes_reclaimed": moved_bytes,
    }
    save_known_state(known_state)
    log.info(f"  State saved for next run comparison")

    return changelog_path


# ── Main ─────────────────────────────────────────────────────

def main():
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log, log_file = setup_logging(run_id)

    log.info("=" * 70)
    log.info("  DAILY DRIVE DUPLICATE FINDER — AUTOMATED RUN")
    log.info(f"  Run ID:   {run_id}")
    log.info(f"  Scan:     {SCAN_ROOT}")
    log.info(f"  Dest:     {DEST_ROOT}")
    log.info(f"  Engine:   {'GPU (CuPy)' if GPU_AVAILABLE else 'CPU (8 threads)'}")
    log.info(f"  GPU:      {GPU_NAME}")
    log.info(f"  Log:      {log_file}")
    log.info("=" * 70)

    start = time.time()
    known_state = load_known_hashes()

    if known_state["last_run"]:
        log.info(f"  Previous run: {known_state['last_run'].get('run_id', 'unknown')}")
        log.info(f"  Previous files: {known_state['last_run'].get('total_files', 0):,}")
    else:
        log.info(f"  First run — no previous state")

    # Stage 1
    candidates, all_files, total_files, total_bytes = scan_files(SCAN_ROOT, log)

    duplicates = {}
    wasted = 0
    moved = []
    errors = []
    moved_bytes = 0

    if candidates:
        # Stage 2
        partial_groups = partial_hash_filter(candidates, log)

        if partial_groups:
            # Stage 3
            duplicates, wasted = full_hash_confirm(partial_groups, log)

            if duplicates:
                # Stage 4
                moved, errors, moved_bytes = move_duplicates(
                    duplicates, SCAN_ROOT, DEST_ROOT, known_state, log
                )
            else:
                log.info("\n  ✓ No confirmed duplicates found!")
        else:
            log.info("\n  ✓ No duplicates after partial hash filtering!")
    else:
        log.info("\n  ✓ No files share the same size — zero potential duplicates!")

    elapsed = time.time() - start

    # Stage 5: Changelog
    changelog = write_daily_changelog(
        run_id, log_file, all_files, duplicates, moved, errors,
        total_files, total_bytes, wasted, moved_bytes, elapsed, known_state, log
    )

    # Also save duplicates.json
    os.makedirs(CATALOG_DIR, exist_ok=True)
    dup_json = os.path.join(CATALOG_DIR, "duplicates.json")
    with open(dup_json, "w", encoding="utf-8") as f:
        json.dump({
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "engine": "GPU" if GPU_AVAILABLE else "CPU",
            "duplicate_sets": len(duplicates),
            "files_moved": len(moved),
            "space_reclaimed": format_size(moved_bytes),
            "moved": moved,
            "errors": errors,
        }, f, indent=2, ensure_ascii=False)

    log.info("")
    log.info("=" * 70)
    log.info(f"  ✅ DAILY RUN COMPLETE — {elapsed:.1f}s")
    log.info(f"  Files scanned:    {total_files:,}")
    log.info(f"  Duplicate sets:   {len(duplicates):,}")
    log.info(f"  Files moved:      {len(moved):,}")
    log.info(f"  Space reclaimed:  {format_size(moved_bytes)}")
    log.info(f"  Changelog:        {changelog}")
    log.info(f"  Log:              {log_file}")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
