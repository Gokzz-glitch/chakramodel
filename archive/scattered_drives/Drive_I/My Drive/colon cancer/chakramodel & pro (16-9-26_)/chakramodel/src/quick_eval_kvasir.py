"""
Backward-compatibility root shim for quick_eval_kvasir.
The canonical location is src/evaluation/quick_eval_kvasir.py.
"""
import os
import sys

from pathlib import Path

# Add repository root, src, and models directories to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
for p in [str(PROJECT_ROOT), str(PROJECT_ROOT / "src"), str(PROJECT_ROOT / "src" / "models")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.evaluation.quick_eval_kvasir import *

if __name__ == "__main__":
    from src.evaluation.quick_eval_kvasir import main
    main()
