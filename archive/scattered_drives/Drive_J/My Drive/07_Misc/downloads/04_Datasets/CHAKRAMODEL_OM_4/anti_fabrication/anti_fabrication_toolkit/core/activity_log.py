"""
activity_log.py — one persistent, HASH-CHAINED, append-only log of EVERY
verification run ever done, across ALL projects, forever.

Why hash-chained: a plain append-only file can still have a line quietly
deleted or edited without anyone noticing. Each entry here includes the
hash of the entry before it (like a mini blockchain), so if any past
entry is altered or removed, every entry after it fails the chain check.
Run `verifyai log --verify` any time to confirm the whole history is
intact.

This file lives outside any project folder, right next to the toolkit
itself, so:
  - you (or a future agent session) can always see the full history
  - nothing is ever "forgotten" just because a chat session ended
  - it's a second, independent trail alongside the signed verdict cards
"""

import os
import json
import time
import hashlib

LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "activity_log.jsonl")

GENESIS_HASH = "0" * 64  # the "previous hash" for the very first entry ever


def _hash_entry(entry_without_hash: dict) -> str:
    payload = json.dumps(entry_without_hash, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def _last_hash() -> str:
    if not os.path.exists(LOG_PATH):
        return GENESIS_HASH
    with open(LOG_PATH) as f:
        lines = f.readlines()
    if not lines:
        return GENESIS_HASH
    last = json.loads(lines[-1])
    return last["entry_hash"]


def append_log(project: str, dataset: str, decision: str, card_path: str, findings: list):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    prev_hash = _last_hash()
    entry = {
        "timestamp_epoch": time.time(),
        "timestamp_human": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "project": project,
        "dataset": dataset,
        "decision": decision,
        "card_path": card_path,
        "findings_summary": findings,
        "prev_hash": prev_hash,
    }
    entry["entry_hash"] = _hash_entry(entry)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def read_log(n: int = 20):
    if not os.path.exists(LOG_PATH):
        print("[LOG] No verification runs recorded yet.")
        return
    with open(LOG_PATH) as f:
        lines = f.readlines()
    print(f"[LOG] Showing last {min(n, len(lines))} of {len(lines)} total runs:")
    print("=" * 70)
    for line in lines[-n:]:
        e = json.loads(line)
        print(f"{e['timestamp_human']} | {e['project']}/{e['dataset']} | {e['decision']}")
        print(f"   card: {e['card_path']}")
    print("=" * 70)


def verify_log_integrity():
    """Walks the whole chain and confirms nothing was altered or deleted."""
    if not os.path.exists(LOG_PATH):
        print("[LOG] No log file yet — nothing to verify.")
        return True
    with open(LOG_PATH) as f:
        lines = f.readlines()

    expected_prev = GENESIS_HASH
    for i, line in enumerate(lines):
        entry = json.loads(line)
        stored_hash = entry.pop("entry_hash")
        recomputed = _hash_entry(entry)
        if recomputed != stored_hash:
            print(f"[LOG] TAMPER DETECTED at entry #{i+1}: content doesn't match its own recorded hash.")
            return False
        if entry["prev_hash"] != expected_prev:
            print(f"[LOG] TAMPER DETECTED at entry #{i+1}: chain link to previous entry is broken "
                  f"(an earlier entry was likely deleted, inserted, or reordered).")
            return False
        expected_prev = stored_hash

    print(f"[LOG] Chain verified intact — all {len(lines)} entries are genuine and in original order.")
    return True
