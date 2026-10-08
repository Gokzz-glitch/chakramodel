#!/usr/bin/env python3
"""Detached, DETECT-ONLY Unity modal-dialog probe for the bmad-loop Unity plugin.

Unity on Linux is an X11 (or XWayland) client, so its run-freezing modal dialogs —
"scene(s) have been modified" (reload / save-before-close), "conflicting scene
changes" — are ordinary X windows. This probe polls xdotool for a *visible*
Unity-owned window whose title matches one of those dialogs and, when it finds one,
**reports it and nothing more**: it NEVER clicks, keys, activates, or closes any
window. The scene-guard (auto-save) and the injected prompt facts are what *prevent*
the modals; this is the last-resort observability net that tells a human one slipped
through and is now freezing the MCP dispatch loop.

Report on a fresh detection (deduped per window id, per probe lifetime):
  1. a JSONL line to ``<run_dir>/unity-dialog-probe.jsonl`` — ``{ts, window, title}``;
  2. a line to ``<run_dir>/ATTENTION`` in the same format as ``gates.notify``;
  3. a best-effort ``notify-send`` desktop notification (guarded by ``shutil.which``,
     gated by ``BMAD_LOOP_UNITY_DIALOG_PROBE_NOTIFY``), mirroring ``gates.notify``.

Lifecycle: launched detached by ``UnityPlugin`` (shared mode: at ``pre_run``;
per_worktree: at ``pre_worktree_setup``) with the project/worktree path in argv, so
``unity_teardown.py``'s ``/proc`` argv scan can find + reap it. It also writes its own
``<run_dir>/unity-dialog-probe.pid`` (pid + start-time identity, via
``runs.write_named_pid``) as the primary reap handle. Self-reaping backstop: it polls
``<run_dir>/engine.pid`` liveness (``runs.engine_alive`` — the same identity-checked
logic the CLI uses) and exits when the engine dies, so an un-reaped probe can never
outlive its run.

Stdlib only, plus bmad-loop's own dep-free process/pid helpers (no third-party deps).
No-op clean exit (0) when there is nothing to watch: ``DISPLAY`` unset, ``xdotool``
absent, or ``BMAD_LOOP_RUN_DIR`` unset (Windows/macOS fall out here — out of scope).

Env (injected by the engine plugin):
  BMAD_LOOP_RUN_DIR                          run dir for outputs + engine.pid liveness
  BMAD_LOOP_UNITY_DIALOG_PROBE_INTERVAL_SEC  poll interval seconds     (default 5, min 1)
  BMAD_LOOP_UNITY_DIALOG_PROBE_NOTIFY        1/0 desktop notify        (default 1)
  BMAD_LOOP_UNITY_DIALOG_PROBE_CLASS         xdotool WM_CLASS regex    (default Unity)

NOTE: the exact dialog titles + the "Unity" window class are UNVERIFIED against a live
Linux Editor build — they are best-effort heuristics. Detection is advisory; a miss
degrades to the pre-existing behavior (a human notices the frozen run), never worse.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

# bmad-loop's own dep-free liveness/pid helpers (run under sys.executable, so the
# package is importable — same contract unity_teardown.py relies on for process_host).
from bmad_loop.runs import engine_alive, write_named_pid

PROBE_PID_FILE = "unity-dialog-probe.pid"
PROBE_JSONL = "unity-dialog-probe.jsonl"
ATTENTION_FILE = "ATTENTION"
_TITLE = "Unity modal dialog detected"

# Case-insensitive substrings identifying a run-freezing Unity modal dialog by its
# window title. UNVERIFIED against a live Editor — kept broad + advisory on purpose.
_DIALOG_PATTERNS = (
    "changed on disk",
    "save changes before",
    "conflicting scene changes",
    "scene(s) have been modified",
    "reload the following",
    "do you want to save",
    "unapplied import settings",
)

# Set by the SIGTERM/SIGINT handler so a polite teardown ends the loop promptly.
_stop = False


def _truthy(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _install_signals() -> None:
    """Break the poll loop on SIGTERM/SIGINT so the plugin's polite reap suffices."""

    def _handler(_signum, _frame):
        global _stop
        _stop = True

    for name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, name, None)
        if sig is not None:
            try:
                signal.signal(sig, _handler)
            except (ValueError, OSError):  # pragma: no cover - not the main thread, etc.
                pass


def _interval() -> float:
    try:
        return max(1.0, float(os.environ.get("BMAD_LOOP_UNITY_DIALOG_PROBE_INTERVAL_SEC", "5")))
    except (TypeError, ValueError):
        return 5.0


def _run_xdotool(args: list[str], timeout: float = 10.0) -> subprocess.CompletedProcess:
    return subprocess.run(["xdotool", *args], capture_output=True, text=True, timeout=timeout)


def _unity_window_ids(run) -> list[str]:
    """Ids of *visible* Unity-owned windows (xdotool search by WM_CLASS regex).
    xdotool exits non-zero when nothing matches — that is the normal "no dialog"
    case, not an error. Any launch failure degrades to an empty list."""
    cls = os.environ.get("BMAD_LOOP_UNITY_DIALOG_PROBE_CLASS", "Unity")
    try:
        proc = run(["search", "--onlyvisible", "--class", cls])
    except (subprocess.SubprocessError, OSError):
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip().isdigit()]


def _window_name(run, wid: str) -> str:
    try:
        proc = run(["getwindowname", wid])
    except (subprocess.SubprocessError, OSError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _matches_dialog(name: str) -> bool:
    low = name.lower()
    return any(pattern in low for pattern in _DIALOG_PATTERNS)


def _scan_for_dialogs(run) -> list[tuple[str, str]]:
    """(window id, title) for every visible Unity window whose title matches a known
    modal-dialog phrase. ``run`` is an injectable xdotool runner (for testing)."""
    hits: list[tuple[str, str]] = []
    for wid in _unity_window_ids(run):
        name = _window_name(run, wid)
        if name and _matches_dialog(name):
            hits.append((wid, name))
    return hits


def _report(run_dir: Path, wid: str, name: str, *, notify: bool) -> None:
    """Record one fresh detection: JSONL + ATTENTION + (best-effort) notify-send.
    Every sink is independently guarded — a filesystem or notify failure never stops
    the others, and never raises."""
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        with (run_dir / PROBE_JSONL).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": ts, "window": wid, "title": name}) + "\n")
    except OSError:
        pass
    # ATTENTION line: identical shape to gates.notify's file sink.
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    message = f"window {wid}: {name}"
    try:
        with (run_dir / ATTENTION_FILE).open("a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] {_TITLE}: {message}\n")
    except OSError:
        pass
    # portability: notify-send is Linux-only; the shutil.which guard makes this a
    # no-op where it is absent (mirrors gates.notify).
    if notify and shutil.which("notify-send"):
        try:
            subprocess.run(
                ["notify-send", "--app-name=bmad-loop", _TITLE, message],
                timeout=10,
                capture_output=True,
            )
        except (subprocess.SubprocessError, OSError):
            pass  # desktop notification is best-effort


def _scan_once(run, run_dir: Path, seen: set[str], *, notify: bool) -> int:
    """One scan+report pass. Reports only window ids not already in ``seen`` (dedupe
    repeat detections of the same dialog). Returns the count of NEW reports."""
    reported = 0
    for wid, name in _scan_for_dialogs(run):
        if wid in seen:
            continue
        seen.add(wid)
        _report(run_dir, wid, name, notify=notify)
        reported += 1
    return reported


def _sleep_until_next_poll(interval: float, run_dir: Path) -> None:
    """Sleep ``interval`` in ~1s slices so a SIGTERM or a dead engine is noticed
    within about a second regardless of how long the poll interval is."""
    slept = 0.0
    while not _stop and slept < interval and engine_alive(run_dir):
        time.sleep(min(1.0, interval - slept))
        slept += 1.0


def main() -> int:
    if not os.environ.get("DISPLAY"):
        print("unity_dialog_probe: DISPLAY unset; nothing to probe (exit 0)", file=sys.stderr)
        return 0
    if shutil.which("xdotool") is None:
        print("unity_dialog_probe: xdotool not on PATH; nothing to probe (exit 0)", file=sys.stderr)
        return 0
    rd = (os.environ.get("BMAD_LOOP_RUN_DIR") or "").strip()
    if not rd:
        # Without a run dir we have nowhere to report AND no engine pid to shadow —
        # refuse rather than loop forever as an orphan.
        print(
            "unity_dialog_probe: BMAD_LOOP_RUN_DIR unset; refusing to run with no "
            "engine to shadow (exit 0)",
            file=sys.stderr,
        )
        return 0

    run_dir = Path(rd)
    interval = _interval()
    notify = _truthy(os.environ.get("BMAD_LOOP_UNITY_DIALOG_PROBE_NOTIFY"), True)
    _install_signals()
    # primary reap handle: our own pid + start-time identity (mirrors runs.write_pid).
    try:
        write_named_pid(run_dir / PROBE_PID_FILE, os.getpid())
    except OSError:
        pass

    seen: set[str] = set()
    while not _stop and engine_alive(run_dir):
        _scan_once(_run_xdotool, run_dir, seen, notify=notify)
        _sleep_until_next_poll(interval, run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
