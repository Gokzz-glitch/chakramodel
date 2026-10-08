"""Unit tests for the Unity rollback-quiesce helper (``unity_quiesce.py``).

The helper is shelled out by ``UnityPlugin`` around a failed-attempt rollback: the
``pre`` phase saves + closes open scenes before ``git reset --hard`` rewrites tracked
``.unity`` files (so a shared Editor never raises the run-freezing "scene changed on
disk" modal), and the ``post`` phase refreshes assets afterwards. These drive its
``main()`` with a stubbed Unity-MCP CLI (monkeypatched ``subprocess.run`` + ``which``)
so no real Editor is needed — the plugin-side wiring (env plumbing + the
pre_rollback/post_rollback hooks that invoke it) lives in ``test_engine_plugin.py``.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess

from bmad_loop.plugins import get_plugin


def _load_quiesce():
    path = os.path.join(get_plugin("unity").scripts_dir, "unity_quiesce.py")
    spec = importlib.util.spec_from_file_location("unity_quiesce_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _stub_cli(monkeypatch, mod, responses):
    """Install a fake Unity-MCP CLI. ``responses`` maps a run-tool name to a
    _FakeProc, a callable(cmd)->_FakeProc, or an Exception to raise. Returns the
    list of tool names invoked, in order."""
    tools: list[str] = []

    def fake_run(cmd, **kwargs):
        assert cmd[1] == "run-tool"
        tool = cmd[2]
        tools.append(tool)
        resp = responses.get(tool, _FakeProc(0, "ok"))
        if callable(resp) and not isinstance(resp, BaseException):
            resp = resp(cmd)
        if isinstance(resp, BaseException):
            raise resp
        return resp

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(mod.shutil, "which", lambda c: "/usr/bin/" + c)
    return tools


def _input_of(cmd):
    """The JSON dict passed to a run-tool call via --input (or None)."""
    if "--input" in cmd:
        return json.loads(cmd[cmd.index("--input") + 1])
    return None


# ------------------------------------------------------------------ pre phase


def test_pre_saves_each_open_scene_then_opens_empty(tmp_path, monkeypatch):
    mod = _load_quiesce()
    monkeypatch.setenv("BMAD_LOOP_QUIESCE_PHASE", "pre")
    monkeypatch.setenv("BMAD_LOOP_WORKTREE", str(tmp_path))
    saved = []

    def record_save(cmd):
        saved.append(_input_of(cmd)["openedSceneName"])
        return _FakeProc(0, "ok")

    tools = _stub_cli(
        monkeypatch,
        mod,
        {
            "scene-list-opened": _FakeProc(0, json.dumps(["Assets/Main.unity", "Assets/UI.unity"])),
            "scene-save": record_save,
        },
    )

    assert mod.main() == 0
    # list (probe) → save each scene → close-all via script-execute, in that order
    assert tools == ["scene-list-opened", "scene-save", "scene-save", "script-execute"]
    assert saved == ["Assets/Main.unity", "Assets/UI.unity"]


def test_pre_unresponsive_editor_exits_fast_without_further_calls(tmp_path, monkeypatch, capsys):
    """The scene-list-opened probe failing means the Editor is wedged: skip the whole
    quiesce immediately (exit 1), making no save / script-execute calls. The CLI
    returns rc 0 on a connection-refused, so the transport-error payload — not the rc
    — is what trips the skip here."""
    mod = _load_quiesce()
    monkeypatch.setenv("BMAD_LOOP_QUIESCE_PHASE", "pre")
    monkeypatch.setenv("BMAD_LOOP_WORKTREE", str(tmp_path))
    tools = _stub_cli(
        monkeypatch,
        mod,
        {"scene-list-opened": _FakeProc(0, "Error: connection refused (localhost:8080)")},
    )

    assert mod.main() == 1
    assert tools == ["scene-list-opened"]  # nothing after the probe
    assert "editor unresponsive" in capsys.readouterr().err


def test_pre_scene_named_error_is_not_treated_as_unresponsive(tmp_path, monkeypatch):
    """A scene whose name/path contains 'error' must NOT read as a dead Editor — the
    probe only skips on transport-level phrases, never on scene-list user data. The
    quiesce proceeds: the scene is saved and the close-all still runs."""
    mod = _load_quiesce()
    monkeypatch.setenv("BMAD_LOOP_QUIESCE_PHASE", "pre")
    monkeypatch.setenv("BMAD_LOOP_WORKTREE", str(tmp_path))
    saved = []

    def record_save(cmd):
        saved.append(_input_of(cmd)["openedSceneName"])
        return _FakeProc(0, "ok")

    tools = _stub_cli(
        monkeypatch,
        mod,
        {
            "scene-list-opened": _FakeProc(0, json.dumps(["Assets/UI/ErrorPopup.unity"])),
            "scene-save": record_save,
        },
    )

    assert mod.main() == 0
    assert tools == ["scene-list-opened", "scene-save", "script-execute"]
    assert saved == ["Assets/UI/ErrorPopup.unity"]  # saved, not skipped


def test_pre_probe_timeout_is_treated_as_unresponsive(tmp_path, monkeypatch):
    """A hung probe (subprocess timeout) is a wedged Editor too — fast skip."""
    mod = _load_quiesce()
    monkeypatch.setenv("BMAD_LOOP_QUIESCE_PHASE", "pre")
    monkeypatch.setenv("BMAD_LOOP_WORKTREE", str(tmp_path))
    tools = _stub_cli(
        monkeypatch,
        mod,
        {"scene-list-opened": subprocess.TimeoutExpired(cmd="scene-list-opened", timeout=15)},
    )

    assert mod.main() == 1
    assert tools == ["scene-list-opened"]


def test_pre_tolerates_per_scene_save_failure(tmp_path, monkeypatch, capsys):
    """An individual scene-save failure (untitled scenes throw) is tolerated: the
    other scenes still save and the close-all still runs. Overall success."""
    mod = _load_quiesce()
    monkeypatch.setenv("BMAD_LOOP_QUIESCE_PHASE", "pre")
    monkeypatch.setenv("BMAD_LOOP_WORKTREE", str(tmp_path))

    def flaky_save(cmd):
        name = _input_of(cmd)["openedSceneName"]
        return _FakeProc(1, "cannot save untitled") if name == "Untitled" else _FakeProc(0, "ok")

    tools = _stub_cli(
        monkeypatch,
        mod,
        {
            "scene-list-opened": _FakeProc(0, json.dumps(["Untitled", "Assets/Main.unity"])),
            "scene-save": flaky_save,
        },
    )

    assert mod.main() == 0
    assert tools == ["scene-list-opened", "scene-save", "scene-save", "script-execute"]
    assert "scene-save 'Untitled' failed" in capsys.readouterr().err


def test_pre_unparseable_scene_list_still_closes_all(tmp_path, monkeypatch):
    """If the opened-scene list can't be parsed we skip the (optional) saves but the
    close-all script-execute — the actual modal-avoidance — still runs."""
    mod = _load_quiesce()
    monkeypatch.setenv("BMAD_LOOP_QUIESCE_PHASE", "pre")
    monkeypatch.setenv("BMAD_LOOP_WORKTREE", str(tmp_path))
    tools = _stub_cli(monkeypatch, mod, {"scene-list-opened": _FakeProc(0, "not json at all")})

    assert mod.main() == 0
    assert tools == ["scene-list-opened", "script-execute"]  # no saves, close-all still runs


def test_pre_script_execute_carries_newscene_csharp(tmp_path, monkeypatch):
    mod = _load_quiesce()
    monkeypatch.setenv("BMAD_LOOP_QUIESCE_PHASE", "pre")
    monkeypatch.setenv("BMAD_LOOP_WORKTREE", str(tmp_path))
    seen = {}

    def capture(cmd):
        seen["input"] = _input_of(cmd)
        return _FakeProc(0, "ok")

    _stub_cli(
        monkeypatch,
        mod,
        {"scene-list-opened": _FakeProc(0, "[]"), "script-execute": capture},
    )

    assert mod.main() == 0
    # The IvanMurzak script-execute schema requires csharpCode (+ className/methodName);
    # sending a bare "code" key makes the call fail silently and the modal-avoidance no-op.
    assert "code" not in seen["input"]
    assert (
        "EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single)"
        in seen["input"]["csharpCode"]
    )
    assert seen["input"]["className"] == "BmadQuiesce"
    assert seen["input"]["methodName"] == "Main"


# ----------------------------------------------------------------- post phase


def test_post_refreshes_assets(tmp_path, monkeypatch):
    mod = _load_quiesce()
    monkeypatch.setenv("BMAD_LOOP_QUIESCE_PHASE", "post")
    monkeypatch.setenv("BMAD_LOOP_WORKTREE", str(tmp_path))
    refresh = {}

    def capture(cmd):
        refresh["input"] = _input_of(cmd)
        # refresh gets the wider per-call floor (45s), passed as --timeout ms
        refresh["timeout_ms"] = int(cmd[cmd.index("--timeout") + 1])
        return _FakeProc(0, "ok")

    tools = _stub_cli(monkeypatch, mod, {"assets-refresh": capture})

    assert mod.main() == 0
    assert tools == ["assets-refresh"]
    assert refresh["input"] == {}
    assert refresh["timeout_ms"] >= 45000


def test_post_tolerates_refresh_timeout(tmp_path, monkeypatch, capsys):
    """A refresh timeout is tolerated (exit 1 advisory): the in-editor refresh keeps
    going on its own, and the plugin ignores the rc regardless."""
    mod = _load_quiesce()
    monkeypatch.setenv("BMAD_LOOP_QUIESCE_PHASE", "post")
    monkeypatch.setenv("BMAD_LOOP_WORKTREE", str(tmp_path))
    _stub_cli(
        monkeypatch,
        mod,
        {"assets-refresh": subprocess.TimeoutExpired(cmd="assets-refresh", timeout=45)},
    )

    assert mod.main() == 1
    assert "assets-refresh did not complete" in capsys.readouterr().err


# --------------------------------------------------------------- cli resolution


def test_missing_cli_skips_quiesce(tmp_path, monkeypatch, capsys):
    mod = _load_quiesce()
    monkeypatch.setenv("BMAD_LOOP_QUIESCE_PHASE", "pre")
    monkeypatch.setenv("BMAD_LOOP_WORKTREE", str(tmp_path))
    monkeypatch.setattr(mod.shutil, "which", lambda c: None)

    assert mod.main() == 1
    assert "not found on PATH" in capsys.readouterr().err


def test_call_timeout_env_override(tmp_path, monkeypatch):
    mod = _load_quiesce()
    monkeypatch.setenv("BMAD_LOOP_QUIESCE_PHASE", "pre")
    monkeypatch.setenv("BMAD_LOOP_WORKTREE", str(tmp_path))
    monkeypatch.setenv("BMAD_LOOP_UNITY_QUIESCE_CALL_TIMEOUT", "8000")
    seen = {}

    def capture(cmd):
        seen["ms"] = int(cmd[cmd.index("--timeout") + 1])
        return _FakeProc(0, "[]")

    _stub_cli(monkeypatch, mod, {"scene-list-opened": capture})

    assert mod.main() == 0
    assert seen["ms"] == 8000  # the per-call CLI --timeout honours the env override
