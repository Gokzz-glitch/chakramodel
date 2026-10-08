"""State persistence: the atomic write must survive the transient Windows
sharing violation (WinError 5) a concurrent TUI reader triggers. The retry
lives in platform_util.atomic_replace (unit-tested there); this proves
save_state still rides it end to end."""

from __future__ import annotations

import os

from bmad_loop import platform_util
from bmad_loop.journal import load_state, save_state
from bmad_loop.model import RunState


def test_save_state_retries_transient_sharing_violation(tmp_path, monkeypatch):
    """On win32, os.replace denied by a concurrent reader is retried, not fatal."""
    monkeypatch.setattr(platform_util.sys, "platform", "win32")
    monkeypatch.setattr(platform_util.time, "sleep", lambda _s: None)  # no real backoff

    real_replace = os.replace
    calls = {"n": 0}

    def flaky_replace(src, dst):
        calls["n"] += 1
        if calls["n"] < 3:  # first two collide, third lands
            raise PermissionError(5, "Access is denied")
        real_replace(src, dst)

    monkeypatch.setattr(platform_util.os, "replace", flaky_replace)

    save_state(tmp_path, RunState(run_id="r1", project="p", started_at="2026-07-06T21:00:00"))

    assert calls["n"] == 3
    assert load_state(tmp_path).run_id == "r1"
