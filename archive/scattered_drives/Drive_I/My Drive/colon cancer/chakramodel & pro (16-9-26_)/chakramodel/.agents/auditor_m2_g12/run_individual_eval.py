import subprocess
import sys
import json
import time
from pathlib import Path

REPO_ROOT = Path("M:/chakramodel")
TESTS_DIR = REPO_ROOT / "tests" / "adversarial"

tests = [
    "test_flaw_01_no_skip_connections.py",
    "test_flaw_02_dead_imagenet_head.py",
    "test_flaw_03_dead_code.py",
    "test_flaw_04_oom_fallback.py",
    "test_flaw_05_tta_enabled_by_default.py",
    "test_flaw_06_unguarded_torch_load.py",
    "test_flaw_07_strict_false_state_dict.py",
    "test_flaw_08_conformal_formula_sign.py",
    "test_flaw_09_mc_dropout_collapse.py",
    "test_flaw_10_contradictory_calibration_qhat.py",
    "test_flaw_11_unpinned_dependencies.py",
    "test_flaw_12_ci_lacking_src_coverage.py",
    "test_flaw_13_unrecoverable_training_batches.py",
    "test_flaw_14_headline_metric_artifact_absence.py",
]

results = {}
for t in tests:
    script_path = TESTS_DIR / t
    t0 = time.time()
    res = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    dt = time.time() - t0
    results[t] = {
        "exit_code": res.returncode,
        "stdout": res.stdout,
        "stderr": res.stderr,
        "duration_sec": round(dt, 3)
    }

output_path = REPO_ROOT / ".agents" / "auditor_m2_g12" / "raw_test_runs.json"
output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
print(f"Captured all 14 test executions to {output_path}")
for t, r in results.items():
    print(f"{t}: Exit {r['exit_code']} in {r['duration_sec']}s")
