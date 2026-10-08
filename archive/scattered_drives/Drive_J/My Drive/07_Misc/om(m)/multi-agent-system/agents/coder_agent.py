"""
Coder Agent — reads existing files for context, writes new code,
runs tests, and commits to git. Uses GitHub Models API (free).
"""

import os
import subprocess
from pathlib import Path
from openai import OpenAI

class CoderAgent:
    def __init__(self, project_root: str, client: OpenAI):
        self.root = Path(project_root)
        self.client = client

    def execute(self, task: dict, context: dict, feedback: str = None) -> dict:
        """Given a task, write the code for it and save to disk."""
        file_contents = self._read_relevant_files(task.get("files", []), context)

        system_prompt = """You are an expert software engineer working autonomously.
You write clean, working, production-quality code.
When given a task, return ONLY the file contents to create/modify.
Return as JSON: {"files": [{"path": "relative/path.py", "content": "full file content"}]}
No explanation. No markdown. Only valid JSON."""

        user_prompt = f"""Task: {task['title']}
Description: {task['description']}

Project decisions/architecture:
{context.get('decisions', 'None yet')}

Relevant existing files:
{file_contents}
{f'Reviewer feedback to fix: {feedback}' if feedback else ''}

Write the complete code. Return JSON only."""

        resp = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

        import json
        result = json.loads(resp.choices[0].message.content)
        written = []
        for file_spec in result.get("files", []):
            path = self.root / file_spec["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(file_spec["content"])
            written.append(file_spec["path"])

        return {"task": task, "files_written": written, "raw": result}

    def commit(self, message: str):
        """Stage all changes and commit to git."""
        try:
            subprocess.run(["git", "add", "-A"], cwd=self.root, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"agent: {message}"],
                cwd=self.root, check=True, capture_output=True,
                env={**os.environ, "GIT_AUTHOR_NAME": "AgentBot", "GIT_AUTHOR_EMAIL": "agent@bot.local",
                     "GIT_COMMITTER_NAME": "AgentBot", "GIT_COMMITTER_EMAIL": "agent@bot.local"}
            )
        except subprocess.CalledProcessError as e:
            print(f"Git commit failed: {e.stderr.decode()}")

    def _read_relevant_files(self, files: list, context: dict) -> str:
        """Read the actual content of files relevant to the task."""
        parts = []
        for rel_path in files[:5]:  # max 5 files to stay within token limit
            path = self.root / rel_path
            if path.exists():
                content = path.read_text(errors="ignore")[:3000]  # cap per file
                parts.append(f"=== {rel_path} ===\n{content}")
            else:
                # Check if summary exists in memory index
                summary = context.get("file_summaries", {}).get(rel_path, {}).get("summary", "")
                if summary:
                    parts.append(f"=== {rel_path} (summary) ===\n{summary}")
        return "\n\n".join(parts) or "No existing files for this task yet."
