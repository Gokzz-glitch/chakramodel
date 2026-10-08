"""
harness_core.py — the project-agnostic verification engine.

Nothing in this file knows about ChakraModel or any specific project.
It only knows how to:
  1. plant unpredictable canaries in a dataset folder
  2. run a script live and capture its real stdout with real timestamps
  3. check nonce / canary / count / timing plausibility
  4. sign the verdict so it can't be edited afterward

Used by verifyai.py — you should not need to edit this file for a new
project. Only the registry (config/projects.json, managed via
`verifyai add-project`) changes per project.
"""

import os
import re
import cv2
import sys
import json
import time
import hmac
import hashlib
import secrets
import subprocess
import numpy as np


def _dice(a: np.ndarray, b: np.ndarray) -> float:
    a = (a > 0).astype(np.uint8)
    b = (b > 0).astype(np.uint8)
    inter = (a & b).sum()
    denom = a.sum() + b.sum()
    return 1.0 if denom == 0 else float(2 * inter / denom)


def plant_multi_canary(dataset_root: str, images_subdir="images", masks_subdir="masks"):
    n_canaries = secrets.randbelow(3) + 2  # 2..4
    img_dir = os.path.join(dataset_root, images_subdir)
    mask_dir = os.path.join(dataset_root, masks_subdir)
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(mask_dir, exist_ok=True)

    canaries = []
    for _ in range(n_canaries):
        tag = secrets.token_hex(6)
        name = f"CANARY_{tag}.png"
        rng = np.random.default_rng(int(tag, 16))
        img = rng.integers(0, 255, (448, 448, 3), dtype=np.uint8)
        mask = np.zeros((448, 448), dtype=np.uint8)
        side = 60 + secrets.randbelow(80)
        x0 = secrets.randbelow(448 - side)
        y0 = secrets.randbelow(448 - side)
        mask[y0:y0 + side, x0:x0 + side] = 255

        img_path = os.path.join(img_dir, name)
        mask_path = os.path.join(mask_dir, name)
        cv2.imwrite(img_path, img)
        cv2.imwrite(mask_path, mask)

        canaries.append({
            "filename": name,
            "img_md5": hashlib.md5(open(img_path, "rb").read()).hexdigest(),
            "mask_md5": hashlib.md5(open(mask_path, "rb").read()).hexdigest(),
        })

    nonce = secrets.token_hex(8)
    hmac_key = secrets.token_bytes(32)

    return {
        "nonce": nonce,
        "hmac_key": hmac_key,
        "canaries": canaries,
        "planted_at_epoch": time.time(),
    }


def run_live(script_path: str, extra_env: dict, timeout_sec: int = 3600):
    env = os.environ.copy()
    env.update(extra_env)

    start = time.monotonic()
    proc = subprocess.Popen(
        [sys.executable, script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        bufsize=1,
    )

    lines, arrivals = [], []
    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        if line:
            lines.append(line)
            arrivals.append(time.monotonic() - start)
        if time.monotonic() - start > timeout_sec:
            proc.kill()
            lines.append("\n[HARNESS] TIMEOUT - process killed.\n")
            break

    proc.wait()
    elapsed = time.monotonic() - start
    return "".join(lines), arrivals, elapsed, proc.returncode


def extract_section(full_text: str, section_label: str) -> str:
    if not section_label:
        return full_text
    marker = f"VERIFYING DATASET: {section_label}"
    start = full_text.find(marker)
    if start == -1:
        return ""
    rest = full_text[start:]
    next_pos = rest.find("VERIFYING DATASET:", len(marker))
    return rest if next_pos == -1 else rest[:next_pos]


def verify(full_text: str, arrivals: list, elapsed_sec: float,
           secret: dict, claimed_total_images: int,
           real_total_images_on_disk: int,
           images_per_sec_ceiling: float = 15.0,
           min_plausible_sec: float = 2.0):
    findings = []
    passed = True

    for c in secret["canaries"]:
        name = c["filename"]
        if name not in full_text:
            passed = False
            findings.append(f"FAIL: canary {name} never appears in live output.")
            continue
        m = re.search(rf"{re.escape(name)}.*?([01]\.\d+)", full_text)
        if not m:
            passed = False
            findings.append(f"FAIL: canary {name} mentioned but no dice value found next to it.")
            continue
        val = float(m.group(1))
        findings.append(f"INFO: canary {name} reported dice = {val:.4f}")
        if val > 0.35:
            passed = False
            findings.append(f"FAIL: canary {name} score implausibly high for pure noise input.")

    if secret["nonce"] not in full_text:
        passed = False
        findings.append("FAIL: session nonce absent from live-captured stdout.")
    else:
        findings.append("PASS: nonce present in harness-captured stdout.")

    if claimed_total_images != real_total_images_on_disk:
        passed = False
        findings.append(
            f"FAIL: claimed count ({claimed_total_images}) != actual disk count "
            f"({real_total_images_on_disk})."
        )

    min_required_sec = max(min_plausible_sec, claimed_total_images / images_per_sec_ceiling)
    if elapsed_sec < min_required_sec:
        passed = False
        findings.append(
            f"FAIL: wall-clock elapsed ({elapsed_sec:.2f}s) faster than plausible "
            f"for {claimed_total_images} images (needs >= {min_required_sec:.2f}s)."
        )
    else:
        findings.append(f"PASS: elapsed time ({elapsed_sec:.2f}s) is plausible.")

    if len(arrivals) > 5:
        spread = arrivals[-1] - arrivals[0]
        if spread < 1.0 and claimed_total_images > 20:
            passed = False
            findings.append(
                f"FAIL: all {len(arrivals)} output lines arrived within {spread:.3f}s "
                f"of each other — real per-image logging should be spread out."
            )

    return {"pass": passed, "findings": findings, "elapsed_sec": elapsed_sec,
            "n_output_lines": len(arrivals)}


def sign_verdict(verdict: dict, hmac_key: bytes) -> dict:
    payload = json.dumps(verdict, sort_keys=True).encode()
    sig = hmac.new(hmac_key, payload, hashlib.sha256).hexdigest()
    return {"verdict": verdict, "signature": sig}


def check_signature(signed_blob: dict, hmac_key: bytes) -> bool:
    payload = json.dumps(signed_blob["verdict"], sort_keys=True).encode()
    expected = hmac.new(hmac_key, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signed_blob["signature"])


def write_completion_card(verdict_signed: dict, claim: dict, project: str,
                           verdicts_root: str):
    out_dir = os.path.join(verdicts_root, project, claim.get("dataset", "unknown"))
    os.makedirs(out_dir, exist_ok=True)
    decision = "ADMITTED" if verdict_signed["verdict"]["pass"] else "WITHHELD"
    card = {
        "decision": decision,
        "claim": claim,
        "verdict": verdict_signed["verdict"],
        "signature": verdict_signed["signature"],
        "written_at_epoch": time.time(),
    }
    fname = f"{claim.get('metric_name','metric')}_{int(time.time())}.json"
    path = os.path.join(out_dir, fname)
    with open(path, "w") as f:
        json.dump(card, f, indent=2)
    return path, decision
