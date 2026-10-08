"""External-backend discovery proof (the ``bmad_loop.mux_backends`` entry-point scan).

An out-of-tree backend package advertises a module under the
``bmad_loop.mux_backends`` entry-point group; ``_load_external_backends``
imports it (after the builtins, so tmux keeps first registration) and the
module's import-time ``register_multiplexer`` call makes it selectable exactly
like a bundled backend. These tests pin the loader's contract: discovery,
ordering, and — above all — that a broken third-party distribution degrades to
a recorded, surfaced reason and can never break backend selection.

Entry points are faked by monkeypatching ``importlib.metadata.entry_points``
through the ``multiplexer`` module's own binding (it imports the module, so the
attribute path is ``m.importlib.metadata``); one test builds a real
``*.dist-info`` on ``sys.path`` to prove the scan works against genuine
packaging metadata, not just our fake.
"""

from __future__ import annotations

import sys

import pytest

# Reuse the registry-isolation fixture where it lives; importing it into this
# module's namespace is how pytest shares a non-conftest fixture across files.
from test_backend_registry import fresh_registry  # noqa: F401

from bmad_loop.adapters import multiplexer as m
from bmad_loop.adapters.tmux_backend import TmuxMultiplexer


class _FakeEntryPoint:
    """Duck-typed stand-in for importlib.metadata.EntryPoint: the loader only
    touches ``.name`` and ``.load()``."""

    def __init__(self, name, load):
        self.name = name
        self._load = load

    def load(self):
        return self._load()


@pytest.fixture
def scan_registry(fresh_registry, monkeypatch):  # noqa: F811 — fixture, not a redefinition
    """fresh_registry with the externals scan re-armed (the base fixture parks it
    as already-loaded so installed adapters can't leak into builtin tests).
    Yields a hook: call it with fake entry points (or an exception to raise from
    the scan itself) and the next selection performs that scan."""

    def arm(*eps, scan_error: Exception | None = None):
        def fake_entry_points(*, group):
            assert group == m.MUX_BACKENDS_GROUP
            if scan_error is not None:
                raise scan_error
            return list(eps)

        monkeypatch.setattr(m.importlib.metadata, "entry_points", fake_entry_points)
        m._EXTERNALS_LOADED = False
        m._EXTERNAL_ERRORS.clear()
        m.get_multiplexer.cache_clear()

    yield fresh_registry, arm


def test_entry_point_backend_registers_and_is_selectable(scan_registry, monkeypatch):
    """The pip-install-and-go path: the entry point's module import registers the
    backend; it lists in detect_multiplexers and a forced name selects it."""
    registry, arm = scan_registry
    sentinel = object()

    def load():
        registry.register_multiplexer("extmux", lambda p: False, lambda: sentinel)
        return None  # the loader ignores the return value; import side effect is the contract

    arm(_FakeEntryPoint("extmux", load))
    monkeypatch.setenv("BMAD_LOOP_MUX_BACKEND", "extmux")
    registry.get_multiplexer.cache_clear()
    assert registry.get_multiplexer() is sentinel
    assert registry.external_backend_errors() == {}
    monkeypatch.delenv("BMAD_LOOP_MUX_BACKEND")
    registry.get_multiplexer.cache_clear()
    rows = {r.name: r for r in registry.detect_multiplexers()}
    assert "extmux" in rows


def test_externals_load_after_builtins(scan_registry):
    """Ordering guarantee: builtins register first, so tmux keeps first-wins on a
    name collision and POSIX default selection is unchanged by installing an
    adapter. The external lands after both builtins in the registry."""
    registry, arm = scan_registry

    def load():
        registry.register_multiplexer("extmux", lambda p: True, lambda: object())

    arm(_FakeEntryPoint("extmux", load))
    registry._select()
    names = [name for name, _, _ in registry._BACKENDS]
    assert names.index("tmux") < names.index("extmux")


def test_broken_entry_point_degrades_and_is_recorded(scan_registry, monkeypatch):
    """A distribution whose import blows up must not break selection: tmux is
    still selected, and the failure is recorded for mux/validate to show."""
    registry, arm = scan_registry

    def boom():
        raise ImportError("No module named 'ghost_dependency'")

    arm(_FakeEntryPoint("brokenmux", boom))
    monkeypatch.setattr(sys, "platform", "linux")
    backend, name, _reason = registry._select()
    assert isinstance(backend, TmuxMultiplexer) and name == "tmux"
    errors = registry.external_backend_errors()
    assert list(errors) == ["brokenmux"]
    assert "ghost_dependency" in errors["brokenmux"]


def test_one_broken_package_does_not_hide_the_rest(scan_registry, monkeypatch):
    """Per-entry isolation: the loader keeps importing after a failure, so a
    working adapter still registers alongside a broken one."""
    registry, arm = scan_registry
    sentinel = object()

    def boom():
        raise RuntimeError("half-installed")

    def load():
        registry.register_multiplexer("goodmux", lambda p: False, lambda: sentinel)

    arm(_FakeEntryPoint("brokenmux", boom), _FakeEntryPoint("goodmux", load))
    monkeypatch.setenv("BMAD_LOOP_MUX_BACKEND", "goodmux")
    registry.get_multiplexer.cache_clear()
    assert registry.get_multiplexer() is sentinel
    assert list(registry.external_backend_errors()) == ["brokenmux"]


def test_scan_failure_degrades(scan_registry, monkeypatch):
    """Even the entry-point enumeration itself blowing up (exotic sys.path /
    importlib state) leaves selection working, with the scan failure recorded."""
    registry, arm = scan_registry
    arm(scan_error=RuntimeError("metadata index corrupt"))
    monkeypatch.setattr(sys, "platform", "linux")
    backend, name, _reason = registry._select()
    assert isinstance(backend, TmuxMultiplexer) and name == "tmux"
    assert "<entry-point scan>" in registry.external_backend_errors()


def test_scan_runs_once_per_process(scan_registry):
    """The loaded-flag is set up front: a second selection does not re-scan (a
    third-party import failure is not transient; re-importing would re-fail on
    every selection)."""
    registry, arm = scan_registry
    calls = []

    def load():
        calls.append(1)

    arm(_FakeEntryPoint("extmux", load))
    registry._select()
    registry.get_multiplexer.cache_clear()
    registry._select()
    assert len(calls) == 1


def test_mux_command_surfaces_load_failures(scan_registry, monkeypatch, capsys, tmp_path):
    """`bmad-loop mux` names a failed external package — the one place an operator
    looks when an installed backend is missing from the table."""
    import argparse

    from bmad_loop import cli

    _registry, arm = scan_registry

    def boom():
        raise ImportError("No module named 'ghost_dependency'")

    arm(_FakeEntryPoint("brokenmux", boom))
    monkeypatch.setattr(sys, "platform", "linux")
    args = argparse.Namespace(project=tmp_path, action=None, name=None, clear=False, force=False)
    assert cli.cmd_mux(args) == 0
    captured = capsys.readouterr()
    assert "brokenmux" in captured.err
    assert "ghost_dependency" in captured.err
    assert "tmux" in captured.out  # the table itself still renders


def test_real_dist_info_metadata_is_discovered(
    fresh_registry, monkeypatch, tmp_path  # noqa: F811 — fixture, not a redefinition
):
    """End-to-end against genuine packaging metadata: a real ``*.dist-info`` +
    module on sys.path is found by the unpatched importlib scan and its import
    registers the backend — proving the group name and value convention work
    outside our fakes."""
    site = tmp_path / "site"
    site.mkdir()
    (site / "extmux_backend.py").write_text(
        "from bmad_loop.adapters.multiplexer import register_multiplexer\n"
        "class _Probe:\n"
        "    pass\n"
        "register_multiplexer('extmux-real', lambda p: False, _Probe)\n",
        encoding="utf-8",
    )
    dist = site / "extmux-0.1.dist-info"
    dist.mkdir()
    (dist / "METADATA").write_text("Metadata-Version: 2.1\nName: extmux\nVersion: 0.1\n")
    (dist / "entry_points.txt").write_text(
        "[bmad_loop.mux_backends]\nextmux = extmux_backend\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(site))
    fresh_registry._EXTERNALS_LOADED = False  # re-arm the (real) scan
    fresh_registry._select()
    assert fresh_registry.external_backend_errors().get("extmux") is None
    assert "extmux-real" in [name for name, _, _ in fresh_registry._BACKENDS]
