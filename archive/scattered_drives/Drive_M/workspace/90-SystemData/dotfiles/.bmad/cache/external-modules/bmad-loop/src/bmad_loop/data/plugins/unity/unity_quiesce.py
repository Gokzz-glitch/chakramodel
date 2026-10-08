#!/usr/bin/env python3
"""Rollback quiesce for the bmad-loop Unity engine plugin.

Called by ``UnityPlugin`` around a failed-attempt rollback, in two phases:

  pre  (before ``verify.safe_rollback`` runs ``git reset --hard``): save every
       open scene, then open an empty untitled scene so no tracked ``.unity`` file
       is open when the reset rewrites it. A shared Editor holding a *dirty* scene
       that the reset changes on disk raises a modal "scene changed on disk —
       Reload/Cancel" dialog that freezes ``EditorApplication.update`` and every
       Unity-MCP tool dispatch — this closes that window before it can open.
  post (after the reset rewrote the tracked tree): refresh assets so the Editor
       drops its stale in-memory copies and re-imports the reverted files.

Only the IvanMurzak MCP CLI is driven (the plugin skips this script for any other
MCP). Everything here is BEST EFFORT and never blocks the rollback:

  * the pre phase opens with a ``scene-list-opened`` call that doubles as a wedge
    probe — if the Editor is unresponsive (already showing a modal, or its update
    loop is wedged) that call fails/hangs, and we skip immediately at the cost of
    one call timeout rather than waiting out the whole quiesce budget;
  * every subprocess call carries BOTH the CLI's own ``--timeout`` and a
    subprocess-level ``timeout=`` kill, so a hung call can't deadlock;
  * per-scene saves tolerate failures (an untitled scene throws — expected);
  * exit codes are advisory: the plugin ignores the rc. The hard no-deadlock
    guarantee is these per-call timeouts plus the plugin's overall
    ``quiesce_timeout_sec`` kill of this whole process.

Env knobs (all optional except the phase, which the plugin always sets):
  BMAD_LOOP_QUIESCE_PHASE                   pre | post                (default pre)
  BMAD_LOOP_WORKTREE                        project the Editor has open (falls back to REPO_ROOT)
  BMAD_LOOP_REPO_ROOT                       main repo root
  UNITY_MCP_CLI                             IvanMurzak CLI binary     (default unity-mcp-cli)
  BMAD_LOOP_UNITY_QUIESCE_CALL_TIMEOUT      per-call budget, ms       (default 15000)

NOTE: the exact IvanMurzak CLI tool names (``scene-list-opened`` / ``scene-save`` /
``script-execute`` / ``assets-refresh``) and their ``--input`` schemas move between
releases — verify against the version installed in your project and override the
project-local plugin copy of this script if they differ. Because everything is
best-effort, a name/schema mismatch degrades to "quiesce skipped", never a crash.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

# per-call subprocess kill = the CLI --timeout plus this margin, so the CLI gets a
# chance to return its own clean "timed out" before we hard-kill the process.
_SUBPROC_MARGIN_SEC = 5.0
# default per-call CLI budget (ms) when BMAD_LOOP_UNITY_QUIESCE_CALL_TIMEOUT is unset.
_DEFAULT_CALL_TIMEOUT_MS = 15000
# assets-refresh re-imports the whole reverted tree and legitimately takes longer
# than a scene op, so give it a wider floor than the per-call default.
_REFRESH_CALL_TIMEOUT_MS = 45000

# Transport/health phrases in the scene-list output that mean the Editor isn't
# answering — the CLI returns rc 0 on a connection-refused, so the wedge probe can't
# trust rc alone. These are deliberately NARROWER than unity_ready.py's marker set:
# the probe's payload is a scene *list* whose contents are user data, so the generic
# "error" / "not found" are excluded — a scene named "ErrorPopup.unity" must never
# read as a dead Editor and silently skip the quiesce.
_PROBE_ERROR_MARKERS = ("refused", "internal server error", "is null", "timed out")

# C# executed via script-execute to close every open scene without a save prompt:
# NewScene(EmptyScene, Single) replaces all open scenes with one fresh untitled
# empty scene, which is not dirty — so no tracked scene is open during the reset.
_QUIESCE_CSHARP = (
    "using UnityEditor.SceneManagement; "
    "public class BmadQuiesce { "
    "public static string Main() { "
    "EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single); "
    'return "ok"; } }'
)


def _project() -> str:
    return os.environ.get("BMAD_LOOP_WORKTREE") or os.environ.get("BMAD_LOOP_REPO_ROOT") or "."


def _cli() -> str:
    return os.environ.get("UNITY_MCP_CLI", "unity-mcp-cli")


def _call_timeout_ms() -> int:
    try:
        return max(1000, int(os.environ.get("BMAD_LOOP_UNITY_QUIESCE_CALL_TIMEOUT", "")))
    except ValueError:
        return _DEFAULT_CALL_TIMEOUT_MS


def _run_tool(
    cli: str, tool: str, *, input_json: str | None = None, timeout_ms: int
) -> tuple[int, str]:
    """One ``run-tool`` round-trip. Carries the CLI ``--timeout`` and a subprocess
    kill (``--timeout`` + margin). Returns (raw rc, output-tail); the caller decides
    what the rc/output mean (the CLI's rc is unreliable — 0 on a connection-refused —
    so the wedge probe also inspects the output). Never raises."""
    cmd = [cli, "run-tool", tool, _project()]
    if input_json is not None:
        cmd += ["--input", input_json]
    cmd += ["--timeout", str(timeout_ms)]
    try:
        proc = subprocess.run(
            cmd,
            timeout=timeout_ms / 1000.0 + _SUBPROC_MARGIN_SEC,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return 1, f"run-tool {tool} timed out"
    except OSError as exc:
        return 1, str(exc)
    return proc.returncode, (proc.stdout + proc.stderr).strip()[-500:]


def _unresponsive(output: str) -> bool:
    """True if the scene-list-opened output carries a transport/health phrase — the
    Editor isn't answering — as opposed to a real (even empty) scene list. Only
    transport-level phrases count, so a scene *named* with 'error' is never mistaken
    for a dead Editor (see ``_PROBE_ERROR_MARKERS``)."""
    low = output.lower()
    return any(m in low for m in _PROBE_ERROR_MARKERS)


def _parse_opened_scenes(output: str) -> list[str]:
    """Best-effort extraction of open-scene names from ``scene-list-opened`` output.
    The exact shape is version-specific, so accept the common ones (a JSON array of
    strings, or of objects with a name-ish key, or an object wrapping such a list)
    and return [] on anything unrecognised — step (c) closes every scene regardless,
    so a miss here only skips the (optional) save, never the modal-avoidance."""
    try:
        data = json.loads(output)
    except (ValueError, TypeError):
        return []
    return _scene_names_from(data)


_NAME_KEYS = ("openedSceneName", "sceneName", "name", "Name", "path")
_LIST_KEYS = ("scenes", "openedScenes", "result", "data", "value")


def _scene_names_from(data: object) -> list[str]:
    if isinstance(data, list):
        names: list[str] = []
        for item in data:
            if isinstance(item, str) and item:
                names.append(item)
            elif isinstance(item, dict):
                names.extend(_name_of(item))
        return names
    if isinstance(data, dict):
        for key in _LIST_KEYS:
            if isinstance(data.get(key), list):
                return _scene_names_from(data[key])
        return _name_of(data)  # a single-scene object
    return []


def _name_of(obj: dict) -> list[str]:
    for key in _NAME_KEYS:
        val = obj.get(key)
        if isinstance(val, str) and val:
            return [val]
    return []


def _quiesce_pre(cli: str) -> int:
    call_ms = _call_timeout_ms()
    # (a) list opened scenes — doubles as the wedge probe. A hard failure (rc!=0 /
    # our timeout sentinel) or a transport-error payload (rc 0 on connection-refused)
    # means the Editor is unresponsive; skip the whole quiesce now (cost ~ one call).
    rc, out = _run_tool(cli, "scene-list-opened", timeout_ms=call_ms)
    if rc != 0 or _unresponsive(out):
        print("unity_quiesce: editor unresponsive; skipping quiesce", file=sys.stderr)
        return 1
    # (b) save each open scene so it isn't dirty when the reset rewrites it. Untitled
    # scenes throw (no path) — expected; tolerate every per-scene failure.
    for name in _parse_opened_scenes(out):
        src, _ = _run_tool(
            cli,
            "scene-save",
            input_json=json.dumps({"openedSceneName": name}),
            timeout_ms=call_ms,
        )
        if src != 0:
            print(f"unity_quiesce: scene-save {name!r} failed (tolerated)", file=sys.stderr)
    # (c) close all scenes without a prompt by opening a fresh empty untitled scene,
    # so no tracked scene is open during the reset. Advisory rc.
    _run_tool(
        cli,
        "script-execute",
        input_json=json.dumps(
            {"csharpCode": _QUIESCE_CSHARP, "className": "BmadQuiesce", "methodName": "Main"}
        ),
        timeout_ms=call_ms,
    )
    return 0


def _quiesce_post(cli: str) -> int:
    # refresh assets so the Editor re-imports the reverted tree. Give it the wider
    # refresh floor; tolerate a timeout (the in-editor refresh continues on its own).
    call_ms = max(_call_timeout_ms(), _REFRESH_CALL_TIMEOUT_MS)
    rc, _ = _run_tool(cli, "assets-refresh", input_json="{}", timeout_ms=call_ms)
    if rc != 0:
        print(
            "unity_quiesce: assets-refresh did not complete (refresh continues in-editor)",
            file=sys.stderr,
        )
        return 1
    return 0


def main() -> int:
    phase = (os.environ.get("BMAD_LOOP_QUIESCE_PHASE") or "pre").strip().lower()
    cli = _cli()
    if shutil.which(cli) is None:
        print(
            f"unity_quiesce: {cli!r} not found on PATH; skipping quiesce "
            "(set UNITY_MCP_CLI or override the project-local plugin script)",
            file=sys.stderr,
        )
        return 1
    if phase == "post":
        return _quiesce_post(cli)
    return _quiesce_pre(cli)


if __name__ == "__main__":
    raise SystemExit(main())
