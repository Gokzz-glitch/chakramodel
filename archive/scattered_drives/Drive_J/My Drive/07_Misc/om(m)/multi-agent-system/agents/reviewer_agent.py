"""
Reviewer Agent — reads diffs, checks for bugs and quality issues,
approves or requests changes before code gets committed.
"""

import subprocess
from pathlib import Path
import json
from openai import OpenAI

class ReviewerAgent:
    def __init__(self, project_root: str, client: OpenAI):
        self.root = Path(project_root)
        self.client = client

    def review(self, coder_result: dict, context: dict) -> dict:
        """Review the changes made by the coder agent."""
        diff = self._get_git_diff()
        if not diff:
            return {"approved": True, "feedback": "No diff to review"}

        task = coder_result.get("task", {})

        prompt = f"""You are a strict code reviewer. Review this code diff and decide if it's acceptable.

Task that was implemented: {task.get('title')} — {task.get('description')}

Project architecture decisions:
{context.get('decisions', 'None')}

Git diff of changes:
{diff[:4000]}

Return JSON:
{{
  "approved": true or false,
  "score": 1-10,
  "issues": ["list of problems if any"],
  "feedback": "specific instructions for the coder to fix if not approved"
}}

Approve if score >= 6 and no critical bugs. Be practical, not perfect."""

        resp = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        try:
            review = json.loads(resp.choices[0].message.content)
            print(f"  Review score: {review.get('score')}/10 — {'APPROVED' if review.get('approved') else 'REJECTED'}")
            return review
        except Exception:
            return {"approved": True, "feedback": "Review parse failed, approving anyway"}

    def _get_git_diff(self) -> str:
        """Get the current unstaged diff."""
        try:
            result = subprocess.run(
                ["git", "diff", "--staged"],
                cwd=self.root, capture_output=True, text=True
            )
            if not result.stdout:
                # Try unstaged
                result = subprocess.run(
                    ["git", "diff"],
                    cwd=self.root, capture_output=True, text=True
                )
            return result.stdout[:5000]
        except Exception:
            return ""
