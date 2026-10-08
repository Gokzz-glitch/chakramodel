#!/usr/bin/env python3
"""
Adversarial Detection Test for Flaw 12:
src/ is never linted or tested in CI (.github/workflows/test.yml only checks tests/ notebook ASTs).

Integrity & Regression Hazard:
  In .github/workflows/test.yml, the 'lint' job runs 'flake8 tests/' exclusively, omitting src/.
  The 'test' and 'burn-in' jobs execute only 'python tests/test_notebooks_adversarial.py' (a notebook
  JSON parser). Neither pytest nor genuine unit tests covering src/ (such as tests/test_tracker.py)
  are ever executed in CI. Fatal syntax errors, broken imports, or API regressions in src/
  receive a false green checkmark on every commit.

Exit Codes:
  1: Flaw detected (CI workflow omits src/ from linting or omits unit tests covering src/).
  0: Flaw resolved (CI workflow lints src/ and executes unit tests for application code).
  2: Configuration or target file error.
"""

import argparse
import sys
import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test.yml"


def check_flaw_12(workflow_file: Path) -> int:
    print("=" * 75)
    print("ADVERSARIAL AUDIT: Flaw 12 - CI Workflow Coverage of src/")
    print(f"Target Workflow: {workflow_file}")
    print("=" * 75)

    if not workflow_file.exists():
        print(f"[ERROR] Workflow file not found: {workflow_file}", file=sys.stderr)
        return 2

    try:
        content = workflow_file.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
    except Exception as err:
        print(f"[ERROR] Failed to parse workflow YAML: {err}", file=sys.stderr)
        return 2

    jobs = data.get("jobs", {})
    errors = []

    # 1. Audit Lint Job
    lint_job = jobs.get("lint", {})
    lint_steps = lint_job.get("steps", [])
    src_linted = False
    for step in lint_steps:
        run_cmd = step.get("run", "")
        if "flake8" in run_cmd or "ruff" in run_cmd:
            targets = run_cmd.split()
            if any(t.strip().rstrip("/") == "src" for t in targets):
                src_linted = True

    if not src_linted:
        errors.append("CI 'lint' job runs linter only on 'tests/' — 'src/' is completely unlinted.")

    # 2. Audit Test Job
    test_job = jobs.get("test", {})
    test_steps = test_job.get("steps", [])
    src_tested = False
    for step in test_steps:
        run_cmd = step.get("run", "")
        if "pytest" in run_cmd or "test_tracker.py" in run_cmd:
            src_tested = True

    if not src_tested:
        errors.append(
            "CI 'test' job runs only 'python tests/test_notebooks_adversarial.py'. "
            "Neither pytest nor any unit test covering src/ (e.g. tests/test_tracker.py) is ever executed."
        )

    print(f"  - Linter covers src/:            {src_linted}")
    print(f"  - Unit test suite covers src/:    {src_tested}")

    if errors:
        print(f"\n[FAIL] FLAW 12 DETECTED: CI workflow lacks coverage for application source code:")
        for err in errors:
            print(f"  - {err}")
        print("\nQuality Hazard: Application source code in src/ can have syntax errors, broken imports,")
        print("or regressions while CI continues to pass green because only notebook JSON syntax is checked.")
        return 1
    else:
        print("\n[PASS] Flaw 12 Resolved: CI workflow explicitly lints src/ and executes unit tests.")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Adversarial check for Flaw 12 (CI coverage of src/).")
    parser.add_argument(
        "--target-file",
        type=Path,
        default=None,
        help="Path to workflow file to audit."
    )
    parser.add_argument(
        "--workflow-file",
        type=Path,
        default=DEFAULT_WORKFLOW,
        help=f"Path to test.yml (default: {DEFAULT_WORKFLOW})"
    )
    args = parser.parse_args()

    target = args.target_file or args.workflow_file
    sys.exit(check_flaw_12(target))


if __name__ == "__main__":
    main()
