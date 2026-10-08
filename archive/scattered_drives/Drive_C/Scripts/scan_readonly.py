#!/usr/bin/env python3
"""
Read-only drive scanner: inventory + duplicate detection funnel.

STRICTLY READ-ONLY. Opens files with 'rb' only. Never moves, renames,
deletes, or writes anything outside --out-dir. No git invocation.

Dedup funnel:
  stage 1  inventory      every regular file (path, size, mtime)
  stage 2  size groups    discard unique sizes
  stage 3  head hash      blake2b of first 64 KiB
  stage 4  full hash      blake2b of whole file; confirms duplicates

Inventory lives in SQLite under --work-dir so the report cannot fill
the drive it describes. Point --work-dir at a drive you are NOT
scanning if you want zero write footprint on the scanned volumes.
"""

import argparse
import hashlib
import json
import os
import sqlite3
import stat as statmod
import sys
import time

HEAD_BYTES = 64 * 1024
READ_CHUNK = 1024 * 1024
MIN_DEDUP_SIZE = 4096  # below this, recoverable space is negligible

# Directory names skipped anywhere in the tree.
SKIP_DIR_NAMES = {
    "$recycle.bin", "$sysreset", "system volume information",
    "windows", "winnt", "program files", "program files (x86)",
    "programdata", "recovery", "perflogs", "$windows.~bt",
    "$windows.~ws", "msocache", "onedrivetemp", "inetpub",
    ".git",  # no git interaction of any kind
}

# Filenames skipped (huge, volatile, meaningless to dedup).
SKIP_FILE_NAMES = {
    "hiberfil.sys", "pagefile.sys", "swapfile.sys",
    "dumpstack.log", "dumpstack.log.tmp",
}


def longpath(p):
    """On Windows, bypass the 260-char MAX_PATH limit."""
    if os.name != "nt":
        return p
    p = os.path.abspath(p)
    if p.startswith("\\\\?\\"):
        return p
    if p.startswith("\\\\"):
        return "\\\\?\\UNC\\" + p[2:]
    return "\\\\?\\" + p


def displaypath(p):
    """Strip the \\?\ prefix so reported paths stay readable."""
    if p.startswith("\\\\?\\UNC\\"):
        return "\\\\" + p[8:]
    if p.startswith("\\\\?\\"):
        return p[4:]
    return p


class Stats:
    def __init__(self):
        self.files = 0
        self.bytes = 0
        self.dirs = 0
        self.skipped_dirs = 0
        self.errors = {}          # category -> count
        self.error_samples = {}   # category -> up to 5 paths

    def err(self, category, path):
        self.errors[category] = self.errors.get(category, 0) + 1
        s = self.error_samples.setdefault(category, [])
        if len(s) < 5:
            s.append(displaypath(str(path)))


def classify_error(exc):
    if isinstance(exc, PermissionError):
        return "permission_denied"
    if isinstance(exc, FileNotFoundError):
        return "not_found_or_race"
    if isinstance(exc, NotADirectoryError):
        return "not_a_directory"
    if isinstance(exc, OSError):
        return "oserror_errno_%s" % (exc.errno,)
    return type(exc).__name__


def log(msg, logfile):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    if logfile:
        logfile.write(line + "\n")
        logfile.flush()


def inventory(conn, roots, stats, logf, progress_every):
    cur = conn.cursor()
    batch = []
    t0 = time.time()
    for root in roots:
        log("stage1: walking %s" % displaypath(root), logf)
        for dirpath, dirnames, filenames in os.walk(
                root, topdown=True,
                onerror=lambda e: stats.err(classify_error(e),
                                            getattr(e, "filename", "?"))):
            keep = []
            for d in dirnames:
                if d.lower() in SKIP_DIR_NAMES:
                    stats.skipped_dirs += 1
                else:
                    keep.append(d)
            dirnames[:] = keep
            stats.dirs += 1
            for fn in filenames:
                if fn.lower() in SKIP_FILE_NAMES:
                    continue
                full = os.path.join(dirpath, fn)
                try:
                    st = os.lstat(full)
                except Exception as e:  # noqa: BLE001
                    stats.err(classify_error(e), full)
                    continue
                if not statmod.S_ISREG(st.st_mode):
                    continue
                stats.files += 1
                stats.bytes += st.st_size
                batch.append((full, st.st_size, int(st.st_mtime)))
                if len(batch) >= 5000:
                    cur.executemany(
                        "INSERT INTO files(path,size,mtime) VALUES(?,?,?)", batch)
                    conn.commit()
                    batch = []
                if stats.files % progress_every == 0:
                    el = time.time() - t0
                    log("stage1: %d files, %.2f GiB, %d dirs, %.0f files/s"
                        % (stats.files, stats.bytes / 2**30, stats.dirs,
                           stats.files / el if el else 0), logf)
    if batch:
        cur.executemany("INSERT INTO files(path,size,mtime) VALUES(?,?,?)", batch)
        conn.commit()
    log("stage1 DONE: %d files, %.2f GiB, %d dirs, %d skipped dirs"
        % (stats.files, stats.bytes / 2**30, stats.dirs, stats.skipped_dirs), logf)


def hash_file(path, limit=None):
    h = hashlib.blake2b(digest_size=16)
    remaining = limit
    with open(path, "rb") as fh:
        while True:
            want = READ_CHUNK if remaining is None else min(READ_CHUNK, remaining)
            if want <= 0:
                break
            chunk = fh.read(want)
            if not chunk:
                break
            h.update(chunk)
            if remaining is not None:
                remaining -= len(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", nargs="+", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--deep", action="store_true",
                    help="run stage 4 full hashing (otherwise stop at head hash)")
    ap.add_argument("--progress-every", type=int, default=20000)
    ap.add_argument("--max-dup-sets-reported", type=int, default=2000)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    os.makedirs(args.work_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    logpath = os.path.join(args.out_dir, "scan_%s.log" % stamp)
    logf = open(logpath, "w", encoding="utf-8")

    dbpath = os.path.join(args.work_dir, "inventory_%s.sqlite" % stamp)
    if os.path.exists(dbpath):
        os.unlink(dbpath)
    conn = sqlite3.connect(dbpath)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("CREATE TABLE files(path TEXT, size INTEGER, mtime INTEGER,"
                 " headhash TEXT, fullhash TEXT)")

    stats = Stats()
    roots, missing = [], []
    for r in args.roots:
        rp = longpath(r)
        (roots if os.path.isdir(rp) else missing).append(rp)
    for r in missing:
        log("ROOT UNREACHABLE, skipped: %s" % displaypath(r), logf)

    t_start = time.time()
    inventory(conn, roots, stats, logf, args.progress_every)
    conn.execute("CREATE INDEX idx_size ON files(size)")
    conn.commit()

    # stage 2: size groups
    cand = list(conn.execute(
        "SELECT size, COUNT(*) c FROM files WHERE size >= ? "
        "GROUP BY size HAVING c > 1", (MIN_DEDUP_SIZE,)))
    stage2_files = sum(c for _, c in cand)
    stage2_bytes = sum(s * c for s, c in cand)
    log("stage2 DONE: %d candidate files in %d size groups (%.2f GiB)"
        % (stage2_files, len(cand), stage2_bytes / 2**30), logf)

    # stage 3: head hash
    hashed = 0
    t3 = time.time()
    for size, _c in cand:
        rows = list(conn.execute(
            "SELECT rowid, path FROM files WHERE size=?", (size,)))
        for rowid, path in rows:
            try:
                hh = hash_file(path, HEAD_BYTES)
            except Exception as e:  # noqa: BLE001
                stats.err("read_fail_" + classify_error(e), path)
                continue
            conn.execute("UPDATE files SET headhash=? WHERE rowid=?", (hh, rowid))
            hashed += 1
            if hashed % args.progress_every == 0:
                el = time.time() - t3
                log("stage3: head-hashed %d/%d (%.0f files/s)"
                    % (hashed, stage2_files, hashed / el if el else 0), logf)
    conn.commit()
    conn.execute("CREATE INDEX idx_hh ON files(size, headhash)")
    conn.commit()

    hgroups = list(conn.execute(
        "SELECT size, headhash, COUNT(*) c FROM files "
        "WHERE headhash IS NOT NULL GROUP BY size, headhash HAVING c > 1"))
    stage3_files = sum(c for _, _, c in hgroups)
    log("stage3 DONE: %d head-hashed; %d files survive in %d groups"
        % (hashed, stage3_files, len(hgroups)), logf)

    # stage 4: full hash
    stage4_files = 0
    fgroups = []
    if args.deep:
        done = 0
        t4 = time.time()
        hashed_bytes = 0
        for size, hh, _c in hgroups:
            rows = list(conn.execute(
                "SELECT rowid, path FROM files WHERE size=? AND headhash=?",
                (size, hh)))
            if size <= HEAD_BYTES:
                # head hash already covered the entire file
                for rowid, _p in rows:
                    conn.execute("UPDATE files SET fullhash=? WHERE rowid=?",
                                 (hh, rowid))
                    done += 1
                continue
            for rowid, path in rows:
                try:
                    fh = hash_file(path, None)
                except Exception as e:  # noqa: BLE001
                    stats.err("read_fail_" + classify_error(e), path)
                    continue
                conn.execute("UPDATE files SET fullhash=? WHERE rowid=?",
                             (fh, rowid))
                done += 1
                hashed_bytes += size
                if done % 2000 == 0:
                    el = time.time() - t4
                    log("stage4: full-hashed %d/%d (%.1f MiB/s)"
                        % (done, stage3_files,
                           hashed_bytes / 2**20 / el if el else 0), logf)
        conn.commit()
        conn.execute("CREATE INDEX idx_fh ON files(size, fullhash)")
        conn.commit()
        fgroups = list(conn.execute(
            "SELECT size, fullhash, COUNT(*) c FROM files "
            "WHERE fullhash IS NOT NULL GROUP BY size, fullhash HAVING c > 1 "
            "ORDER BY (size * (c-1)) DESC"))
        stage4_files = sum(c for _, _, c in fgroups)
        log("stage4 DONE: %d full-hashed; %d confirmed duplicate files "
            "in %d sets" % (done, stage4_files, len(fgroups)), logf)

    groups = fgroups if args.deep else [(s, h, c) for s, h, c in hgroups]
    recoverable = sum(s * (c - 1) for s, _h, c in groups)
    dup_files = sum(c - 1 for _s, _h, c in groups)

    # ---- reports ----
    txt = os.path.join(args.out_dir, "scan_report_%s.txt" % stamp)
    nd = os.path.join(args.out_dir, "duplicate_sets_%s.ndjson" % stamp)
    col = "fullhash" if args.deep else "headhash"
    with open(txt, "w", encoding="utf-8") as f:
        f.write("READ-ONLY DRIVE SCAN REPORT\n")
        f.write("generated: %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        f.write("elapsed:   %.1f s\n" % (time.time() - t_start))
        f.write("roots scanned:     %s\n" % ", ".join(displaypath(r) for r in roots))
        f.write("roots unreachable: %s\n"
                % (", ".join(displaypath(r) for r in missing) or "none"))
        f.write("mode: %s\n\n" % ("deep (full hash)" if args.deep else "head hash only"))
        f.write("TOTALS\n")
        f.write("  files scanned : %d\n" % stats.files)
        f.write("  bytes scanned : %d (%.2f GiB)\n" % (stats.bytes, stats.bytes / 2**30))
        f.write("  dirs walked   : %d\n" % stats.dirs)
        f.write("  dirs skipped  : %d\n\n" % stats.skipped_dirs)
        f.write("DEDUP FUNNEL\n")
        f.write("  stage1 inventory   : %d files\n" % stats.files)
        f.write("  stage2 size groups : %d files in %d groups\n" % (stage2_files, len(cand)))
        f.write("  stage3 head hash   : %d files in %d groups\n" % (stage3_files, len(hgroups)))
        if args.deep:
            f.write("  stage4 full hash   : %d files in %d sets\n" % (stage4_files, len(fgroups)))
        f.write("\n  duplicate files (excess copies): %d\n" % dup_files)
        f.write("  recoverable bytes : %d (%.2f GiB)\n\n" % (recoverable, recoverable / 2**30))
        f.write("LARGEST DUPLICATE SETS (by wasted bytes)\n")
        shown = sorted(groups, key=lambda g: g[0] * (g[2] - 1), reverse=True)[:50]
        for size, h, c in shown:
            f.write("  waste=%.3f GiB  size=%d  copies=%d  hash=%s\n"
                    % (size * (c - 1) / 2**30, size, c, h[:16]))
            for (p,) in conn.execute(
                    "SELECT path FROM files WHERE size=? AND %s=? LIMIT 12" % col,
                    (size, h)):
                f.write("      %s\n" % displaypath(p))
        f.write("\nERRORS BY CATEGORY\n")
        if not stats.errors:
            f.write("  none\n")
        for k in sorted(stats.errors, key=lambda k: -stats.errors[k]):
            f.write("  %-28s %d\n" % (k, stats.errors[k]))
            for p in stats.error_samples.get(k, []):
                f.write("      e.g. %s\n" % p)

    written = 0
    with open(nd, "w", encoding="utf-8") as f:
        for size, h, c in sorted(groups, key=lambda g: g[0] * (g[2] - 1),
                                 reverse=True):
            if written >= args.max_dup_sets_reported:
                break
            paths = [displaypath(p) for (p,) in conn.execute(
                "SELECT path FROM files WHERE size=? AND %s=?" % col, (size, h))]
            f.write(json.dumps({"size": size, "hash": h, "copies": c,
                                "wasted_bytes": size * (c - 1),
                                "paths": paths}) + "\n")
            written += 1

    log("reports written: %s | %s (%d dup sets, cap %d)"
        % (txt, nd, written, args.max_dup_sets_reported), logf)
    log("ALL DONE in %.1f s" % (time.time() - t_start), logf)
    logf.close()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
