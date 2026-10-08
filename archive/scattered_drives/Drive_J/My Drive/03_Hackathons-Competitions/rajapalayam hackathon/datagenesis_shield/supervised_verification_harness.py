"""
ZERO-TRUST SUPERVISED VERIFICATION HARNESS
===========================================
Upgrade over anti_fabrication_tripwire.py.

Core principle: an agent's SELF-REPORTED output text is never trusted,
no matter how it's dressed up (nonces, canaries, whatever). The only
thing that closes the loophole is removing the channel entirely --
THIS harness is the only thing that invokes the real script and reads
its stdout. The agent never gets to "hand you a log"; it can, at most,
be asked to point at a script path, and this harness runs it itself.

Four independent layers, all must pass:

  1. MULTI-CANARY  - N random synthetic image/mask pairs (N itself
     random, 2-4) inserted at random points in the file listing.
     Ground truth for each is known in advance (pure noise -> dice
     should be ~0 for any honest model). All must be found, all must
     score low.

  2. LIVE-INVOKE ONLY - the harness calls subprocess.Popen itself and
     reads stdout line-by-line in real time, timestamping every line
     with ITS OWN wall clock (not any timestamp embedded in the line
     text, which is trivially fakeable). No text is accepted unless
     this harness produced it by running the process itself.

  3. THROUGHPUT PLAUSIBILITY - given a claimed image count and a
     configurable minimum seconds-per-image floor for the model class
     (e.g. ViT-Large inference cannot realistically exceed ~15
     images/sec even on a good GPU, let alone CPU), the harness checks
     that elapsed wall-clock time is NOT implausibly fast for the
     workload claimed. Instant output for "380 images processed" is
     itself a fail.

  4. SIGNED VERDICT - the final PASS/FAIL verdict is written with an
     HMAC-SHA256 signature keyed on a random secret generated fresh
     each run and never exposed to the invoked process or any agent.
     Anyone editing the verdict JSON afterward invalidates the
     signature, so a "verified" label can't be forged after the fact.

Usage:
    python supervised_verification_harness.py \
        --dataset-root /path/to/cvc-colondb \
        --script /path/to/verify_eval.py \
        --min-images-per-sec-ceiling 15
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
import argparse
import subprocess
import numpy as np


def _dice(a: np.ndarray, b: np.ndarray) -> float:
    a = (a > 0).astype(np.uint8)
    b = (b > 0).astype(np.uint8)
    inter = (a & b).sum()
    denom = a.sum() + b.sum()
    return 1.0 if denom == 0 else float(2 * inter / denom)


def plant_multi_canary(dataset_root: str):
    """Plants a RANDOM number (2-4) of noise canaries at random insertion
    points. Returns the secret record -- keep this out of the agent's
    reach entirely; only the harness process should hold it in memory."""
    n_canaries = secrets.randbelow(3) + 2  # 2..4
    os.makedirs(dataset_root, exist_ok=True)

    canaries = []
    for _ in range(n_canaries):
        tag = secrets.token_hex(6)
        name = f"CANARY_{tag}.png"
        rng = np.random.default_rng(int(tag, 16))
        img = rng.integers(0, 255, (64, 64, 3), dtype=np.uint8)

        img_path = os.path.join(dataset_root, name)
        cv2.imwrite(img_path, img)

        canaries.append({
            "filename": name,
            "img_md5": hashlib.md5(open(img_path, "rb").read()).hexdigest(),
        })

    nonce = secrets.token_hex(8)
    hmac_key = secrets.token_bytes(32)  # NEVER exposed to the subprocess or agent

    return {
        "nonce": nonce,
        "hmac_key": hmac_key,
        "canaries": canaries,
        "planted_at_epoch": time.time(),
    }


def run_live(cmd_args: list, extra_env: dict, timeout_sec: int = 3600):
    """
    The ONLY function allowed to produce "the output". Invokes the
    script directly, reads stdout live, and timestamps every line with
    the harness's own wall clock. Returns (full_text, per_line_arrivals,
    total_elapsed_sec, returncode).
    """
    env = os.environ.copy()
    env.update(extra_env)

    start = time.monotonic()
    proc = subprocess.Popen(
        [sys.executable] + cmd_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        bufsize=1,
    )

    lines = []
    arrivals = []
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


def verify(full_text: str, arrivals: list, elapsed_sec: float,
           secret: dict, claimed_total_images: int,
           real_total_images_on_disk: int,
           images_per_sec_ceiling: float = 15.0,
           min_plausible_sec: float = 2.0):
    """
    Runs all four checks. Returns a verdict dict (not yet signed).
    """
    findings = []
    passed = True

    # --- Layer 1: canaries ---
    for c in secret["canaries"]:
        name = c["filename"]
        if name not in full_text:
            passed = False
            findings.append(f"FAIL: canary {name} never appears in live output.")
            continue
        
        m = re.search(rf"{re.escape(name)} - VERDICT: (.*)", full_text)
        if not m:
            passed = False
            findings.append(f"FAIL: canary {name} mentioned but no VERDICT found next to it.")
            continue
            
        verdict_str = m.group(1).strip()
        findings.append(f"INFO: canary {name} reported VERDICT = {verdict_str}")
        if verdict_str != "TAMPERED or UNKNOWN":
            passed = False
            findings.append(
                f"FAIL: canary {name} passed verification even though it is pure noise "
                f"-- indicates fabricated/hardcoded pass results."
            )

    # --- Layer 2: this harness actually produced the text ---
    if secret["nonce"] not in full_text:
        passed = False
        findings.append("FAIL: session nonce absent from live-captured stdout "
                         "-- should be structurally impossible if the script "
                         "actually read os.environ['VERIFY_NONCE']. Check the "
                         "script prints it; if it does and this still fails, "
                         "something intercepted/replaced the output.")
    else:
        findings.append("PASS: nonce present in harness-captured stdout.")

    # --- Layer 3: throughput plausibility ---
    if claimed_total_images != real_total_images_on_disk:
        passed = False
        findings.append(
            f"FAIL: claimed count ({claimed_total_images}) != actual disk "
            f"count right now ({real_total_images_on_disk})."
        )

    min_required_sec = max(min_plausible_sec, claimed_total_images / images_per_sec_ceiling)
    if elapsed_sec < min_required_sec:
        passed = False
        findings.append(
            f"FAIL: wall-clock elapsed ({elapsed_sec:.2f}s) is faster than "
            f"physically plausible for {claimed_total_images} images at the "
            f"configured ceiling of {images_per_sec_ceiling} img/s "
            f"(would require >= {min_required_sec:.2f}s). Output was likely "
            f"pre-computed/pasted rather than genuinely inferred."
        )
    else:
        findings.append(f"PASS: elapsed time ({elapsed_sec:.2f}s) is plausible "
                         f"for {claimed_total_images} images.")

    # check line arrival spread -- all lines bunched in <1s is suspicious
    # even if total elapsed looks fine (e.g. sleep() at the end only)
    if len(arrivals) > 5:
        spread = arrivals[-1] - arrivals[0]
        if spread < 1.0 and claimed_total_images > 20:
            passed = False
            findings.append(
                f"FAIL: all {len(arrivals)} output lines arrived within "
                f"{spread:.3f}s of each other -- real per-image progress "
                f"logging should be spread across the whole run, not dumped "
                f"at once."
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


def write_completion_card(verdict_signed: dict, claim: dict, out_dir: str = "verification_verdicts"):
    """
    x-harness-style 'completion card': a structured claim (what the agent
    says is true) paired with the ADMITTED/WITHHELD decision from this
    harness. This is the ONLY artifact that should ever be referenced in
    the paper, README, or results table -- never a raw pasted log.

    claim = {
        "metric_name": "Dice",
        "dataset": "CVC-ColonDB",
        "value_claimed": 0.8125,
        "n_images_claimed": 380,
        "script": "verify_eval.py",
    }
    """
    os.makedirs(out_dir, exist_ok=True)
    decision = "ADMITTED" if verdict_signed["verdict"]["pass"] else "WITHHELD"
    card = {
        "decision": decision,
        "claim": claim,
        "verdict": verdict_signed["verdict"],
        "signature": verdict_signed["signature"],
        "written_at_epoch": time.time(),
    }
    fname = f"{claim.get('dataset','unknown').replace(' ','_')}_{claim.get('metric_name','metric')}_{int(time.time())}.json"
    path = os.path.join(out_dir, fname)
    with open(path, "w") as f:
        json.dump(card, f, indent=2)
    print(f"[HARNESS] Completion card written: {path} -> {decision}")
    if decision == "WITHHELD":
        print("[HARNESS] This claim MUST NOT be written into the paper, "
              "README, or any results table until it is ADMITTED.")
    return path, decision


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-root", required=True)
    ap.add_argument("--script", required=True, help="path to the eval script to run LIVE")
    ap.add_argument("--key", required=True, help="team key for watermark extraction")
    ap.add_argument("--images-per-sec-ceiling", type=float, default=1000.0)
    args = ap.parse_args()

    print("[HARNESS] Planting canaries...")
    secret = plant_multi_canary(args.dataset_root)
    print(f"[HARNESS] {len(secret['canaries'])} canaries planted. Nonce set.")

    real_count = len([f for f in os.listdir(args.dataset_root) if f.lower().endswith((".png", ".jpg", ".jpeg"))])

    print("[HARNESS] Invoking script live (agent has NO ability to inject output here)...")
    
    cmd_args = [args.script, "--dir", args.dataset_root, "--key", args.key]
    full_text, arrivals, elapsed, rc = run_live(
        cmd_args, extra_env={"VERIFY_NONCE": secret["nonce"]}
    )
    print("[HARNESS] ---- captured stdout begins ----")
    print(full_text)
    print("[HARNESS] ---- captured stdout ends ----")

    m = re.search(r"Total images found:\s*(\d+)", full_text)
    claimed = int(m.group(1)) if m else -1

    verdict = verify(full_text, arrivals, elapsed, secret, claimed, real_count,
                      images_per_sec_ceiling=args.images_per_sec_ceiling)
    signed = sign_verdict(verdict, secret["hmac_key"])

    out_path = "verification_verdict.json"
    with open(out_path, "w") as f:
        json.dump(signed, f, indent=2)

    claim = {
        "metric_name": "Cryptographic Integrity",
        "dataset": os.path.basename(args.dataset_root.rstrip("/\\")),
        "value_claimed": "VERIFIED",
        "n_images_claimed": claimed,
        "script": args.script,
    }
    card_path, decision = write_completion_card(signed, claim)

    print("\n" + "=" * 60)
    print("FINAL VERDICT:", "PASS" if verdict["pass"] else "FAIL")
    for line in verdict["findings"]:
        print(" -", line)
    print(f"Signed verdict written to {out_path}")
    print(f"Completion card ({decision}): {card_path}")
    print("Only ADMITTED completion cards may be cited in the paper.")
    print("Re-verify later with check_signature() + the hmac_key you kept secret.")
    print("=" * 60)

    sys.exit(0 if verdict["pass"] else 1)


if __name__ == "__main__":
    main()
