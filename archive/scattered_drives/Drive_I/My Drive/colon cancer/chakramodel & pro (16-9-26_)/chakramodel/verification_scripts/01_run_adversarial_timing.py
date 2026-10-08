#!/usr/bin/env python3
"""
Measure actual runtime and exit status of the 14 adversarial detection scripts.

Replaces the second-hand 3.71 s / 3.98 s figures that Paper 2 currently quotes
from the challenger and auditor agents without having run anything.

Run from the repository root:
    .\.venv\Scripts\python.exe verification_scripts\01_run_adversarial_timing.py

Writes: verification_results/adversarial_timing.json  (and prints a summary)

Read-only with respect to the repository: it executes the test scripts as
subprocesses exactly as the original harness did, and writes only into
verification_results/.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TESTDIR = REPO / "tests" / "adversarial"
OUTDIR = REPO / "verification_results"
OUTDIR.mkdir(exist_ok=True)

# The fourteen flaw tests, in order. The runner and the dim/param audit are
# deliberately excluded: the audit is NOT one of the fourteen patch proofs
# (Paper 2 sec 7), and conflating them would overstate the suite's capability.
tests = sorted(p for p in TESTDIR.glob("test_flaw_*.py"))

print(f"Python     : {sys.version.split()[0]}")
print(f"Executable : {sys.executable}")
print(f"Test dir   : {TESTDIR}")
print(f"Found      : {len(tests)} flaw tests\n")

if len(tests) != 14:
    print(f"!! WARNING: expected 14 flaw tests, found {len(tests)}.")
    print("!! Report this rather than proceeding as though it were 14.\n")

results = []
suite_start = time.perf_counter()

for path in tests:
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=600,
    )
    elapsed = time.perf_counter() - t0

    stdout = proc.stdout or ""
    # Does the test import torch at all, and does it construct anything?
    src = path.read_text(encoding="utf-8", errors="replace")
    results.append({
        "test": path.name,
        "returncode": proc.returncode,
        "seconds": round(elapsed, 4),
        "stdout_bytes": len(stdout),
        "stdout_head": stdout[:400],
        "stderr_head": (proc.stderr or "")[:400],
        "imports_torch": "import torch" in src,
        # crude but honest indicators of behavioural testing
        "mentions_forward_pass": any(s in src for s in ("forward(", ".cuda", "device=")),
        "mentions_create_model": "create_model" in src,
    })
    print(f"{path.name:<52} rc={proc.returncode:<3} {elapsed:7.3f}s")

suite_total = time.perf_counter() - suite_start

summary = {
    "python_version": sys.version.split()[0],
    "executable": sys.executable,
    "n_tests": len(tests),
    "suite_wall_seconds_sequential": round(suite_total, 4),
    "sum_of_individual_seconds": round(sum(r["seconds"] for r in results), 4),
    "n_returncode_0": sum(1 for r in results if r["returncode"] == 0),
    "n_returncode_nonzero": sum(1 for r in results if r["returncode"] != 0),
    "n_importing_torch": sum(1 for r in results if r["imports_torch"]),
    "results": results,
}

out = OUTDIR / "adversarial_timing.json"
out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

print("\n" + "=" * 66)
print(f"Total wall time (sequential) : {suite_total:.3f} s")
print(f"Sum of individual times      : {summary['sum_of_individual_seconds']:.3f} s")
print(f"Exit 0                       : {summary['n_returncode_0']} / {len(tests)}")
print(f"Exit non-zero                : {summary['n_returncode_nonzero']} / {len(tests)}")
print(f"Tests importing torch        : {summary['n_importing_torch']} / {len(tests)}")
print("=" * 66)
print(f"\nWrote {out}")
print("\nNOTE: exit-code semantics differ per test (several use 1 = 'flaw")
print("detected'). Do not read 'exit 0' as 'pass' without checking each")
print("test's own documented convention -- see test_flaw_09:13 for an example.")
