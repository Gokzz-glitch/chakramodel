"""
Memory Agent — indexes project files, summarizes them, stores context
so every agent session picks up exactly where the last one left off.
"""

import json
import os
from datetime import datetime
from pathlib import Path

IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".memory", "venv", ".venv", "dist", "build"}
IGNORED_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".lock", ".bin"}
MEMORY_DIR = ".memory"

class MemoryAgent:
    def __init__(self, project_root: str):
        self.root = Path(project_root)
        self.memory_path = self.root / MEMORY_DIR
        self.memory_path.mkdir(exist_ok=True)
        self.index_file = self.memory_path / "index.json"
        self.history_file = self.memory_path / "history.json"

    def load_full_context(self) -> dict:
        """Load everything an agent needs to understand the project."""
        return {
            "file_summaries": self._load_index(),
            "history": self._load_history(limit=20),
            "decisions": self._read_file("DECISIONS.md"),
            "progress": self._read_file("PROGRESS.md"),
            "todo": self._read_file("TODO.md"),
        }

    def update_progress(self, completed_tasks: list, log: list):
        """After each sprint, update PROGRESS.md and history."""
        # Update history
        history = self._load_history()
        history.append({
            "date": datetime.now().isoformat(),
            "tasks": [t["title"] for t in completed_tasks],
            "log": log[-10:],  # last 10 log lines
        })
        history = history[-50:]  # keep last 50 sessions
        self._write_json(self.history_file, history)

        # Update PROGRESS.md
        progress_path = self.root / "PROGRESS.md"
        existing = progress_path.read_text() if progress_path.exists() else ""
        date_str = datetime.now().strftime("%Y-%m-%d")
        new_entries = "\n".join(f"- {t['title']}" for t in completed_tasks)
        new_section = f"\n## {date_str}\n{new_entries}\n"
        progress_path.write_text(new_section + existing)

        # Re-index files that changed
        self._index_project()

    def _index_project(self):
        """Walk the project and summarize each file into index.json."""
        index = self._load_index()
        for path in self.root.rglob("*"):
            if path.is_file() and self._should_index(path):
                rel = str(path.relative_to(self.root))
                mtime = path.stat().st_mtime
                if rel not in index or index[rel].get("mtime") != mtime:
                    index[rel] = {
                        "mtime": mtime,
                        "size": path.stat().st_size,
                        "summary": self._quick_summary(path),
                    }
        self._write_json(self.index_file, index)
        return index

    def _quick_summary(self, path: Path) -> str:
        """Extract a lightweight summary without calling the LLM."""
        try:
            content = path.read_text(errors="ignore")
            lines = [l.strip() for l in content.splitlines() if l.strip()]
            # First 3 non-empty lines
            preview = " | ".join(lines[:3])
            return preview[:200]
        except Exception:
            return "(binary or unreadable)"

    def _should_index(self, path: Path) -> bool:
        parts = set(path.parts)
        if parts & IGNORED_DIRS:
            return False
        if path.suffix in IGNORED_EXTS:
            return False
        if path.stat().st_size > 200_000:  # skip files > 200KB
            return False
        return True

    def _load_index(self) -> dict:
        return self._read_json(self.index_file) or {}

    def _load_history(self, limit: int = 50) -> list:
        data = self._read_json(self.history_file) or []
        return data[-limit:]

    def _read_file(self, name: str) -> str:
        p = self.root / name
        return p.read_text() if p.exists() else ""

    def _read_json(self, path: Path):
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                return None
        return None

    def _write_json(self, path: Path, data):
        path.write_text(json.dumps(data, indent=2))
