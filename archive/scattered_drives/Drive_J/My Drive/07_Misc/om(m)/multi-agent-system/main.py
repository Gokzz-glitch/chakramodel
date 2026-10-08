"""
main.py — Entry point for the autonomous multi-agent system.
Run locally: python main.py
Run automatically: GitHub Actions triggers this daily.
"""

import os
import sys
from agents.orchestrator import Orchestrator

def main():
    project_root = os.environ.get("PROJECT_ROOT", ".")

    # Validate GitHub token exists
    if not os.environ.get("GITHUB_TOKEN"):
        print("ERROR: Set GITHUB_TOKEN environment variable")
        print("Get your free token at: github.com/settings/tokens")
        sys.exit(1)

    print("Starting autonomous agent sprint...")
    orchestrator = Orchestrator(project_root)
    log = orchestrator.run_daily_sprint()

    print(f"\nSprint complete. {len(log)} log entries.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
