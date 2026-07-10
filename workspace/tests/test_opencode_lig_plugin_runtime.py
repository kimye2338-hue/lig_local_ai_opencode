# -*- coding: utf-8 -*-
"""Regression checks for OpenCodeLIG's automatic plugin bridges.

These are static/runtime-contract checks for the parts that make the user-facing
"just use it" behavior work: hamster status, Obsidian autosave, memory injection,
command guard, and pending diagnostics.
"""
from __future__ import annotations

from pathlib import Path

from agent_ops.release_contracts import (
    AUTOSAVE_REQUIRED_MARKERS,
    HAMSTER_EVENT_BRIDGE_MARKERS,
    HAMSTER_LEGACY_MARKERS,
    LAUNCHER_DRIVE_ROOT_FALLBACK,
    LAUNCHER_FAST_RUNTIME_MARKERS,
    LAUNCHER_HAMSTER_MARKERS,
    PLUGIN_SYNC_GLOB,
    REQUIRED_PLUGIN_FILES,
)

WS = Path(__file__).resolve().parents[1]
REPO = WS.parent


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_launcher_keeps_opencode_lig_plugins_loadable_and_crlf() -> None:
    launcher = WS / "RUN_OPENCODE_LIG.bat"
    raw = launcher.read_bytes()
    text = raw.decode("utf-8", errors="replace")

    assert b"\n" not in raw.replace(b"\r\n", b""), "RUN_OPENCODE_LIG.bat must be CRLF-only"
    assert "OPENCODE_PURE=1" not in text
    assert "set \"OPENCODE_PURE=\"" in text
    assert "--pure" not in text.lower()
    assert "OPENCODE_DISABLE_DEFAULT_PLUGINS=1" in text
    assert "LIG_AGENTOPS_HOME=%AGENTOPS_HOME%" in text


def test_launcher_uses_fast_runtime_and_blocks_external_startup_waits() -> None:
    text = read(WS / "RUN_OPENCODE_LIG.bat")
    run_idx = text.index("\"%OCODE_EXE%\" %*")

    for marker in LAUNCHER_FAST_RUNTIME_MARKERS:
        assert marker in text
        assert text.index(marker) < run_idx
    for marker in [
        'set "OPENCODE_FAST_CONFIG=%OPENCODE_FAST_BASE%\\config"',
        'set "OPENCODE_FAST_DATA=%OPENCODE_FAST_BASE%\\data"',
        'set "OPENCODE_FAST_CACHE=%OPENCODE_FAST_BASE%\\cache"',
        'set "OPENCODE_CONFIG=%AGENTOPS_HOME%\\opencode.json"',
        'set "NPM_CONFIG_FETCH_TIMEOUT=1000"',
        'set "NPM_CONFIG_FETCH_RETRIES=0"',
        'set "BUN_INSTALL_CACHE_DIR=%OPENCODE_FAST_CACHE%\\bun"',
        'set "HTTP_PROXY="',
        'set "HTTPS_PROXY="',
        'set "ALL_PROXY="',
    ]:
        assert marker in text
        assert text.index(marker) < run_idx
    assert "set \"OPENCODE_PURE=1\"" not in text
    assert "%OPENCODE_USERDATA%\\data" in text
    assert "robocopy" in text
    assert 'if not exist "%OPENCODE_FAST_DATA%\\*"' in text
    assert "/XO" in text


def test_launcher_preserves_project_dir_and_only_falls_back_for_unsafe_starts() -> None:
    text = read(WS / "RUN_OPENCODE_LIG.bat")

    assert "if not defined LIG_PROJECT_DIR (\n  set \"LIG_PROJECT_DIR=%CD%\"\n)" in text
    assert "if /I \"%LIG_PROJECT_DIR%\"==\"%USERPROFILE%\" set \"LIG_PROJECT_DIR=%AGENTOPS_HOME%\"" in text
    assert "if /I \"%LIG_PROJECT_DIR%\"==\"%WINDIR%\\System32\" set \"LIG_PROJECT_DIR=%AGENTOPS_HOME%\"" in text
    assert "if /I \"%LIG_PROJECT_DIR%\"==\"%WINDIR%\\SysWOW64\" set \"LIG_PROJECT_DIR=%AGENTOPS_HOME%\"" in text
    assert LAUNCHER_DRIVE_ROOT_FALLBACK in text
    assert 'if /I "%%~fI"=="%%~dI\\\\"' not in text
    assert 'set "LIG_PROJECT_DIR=%AGENTOPS_HOME%"' not in text.splitlines()


def test_launcher_starts_hamster_directly_from_real_ui_path() -> None:
    text = read(WS / "RUN_OPENCODE_LIG.bat")

    assert "hamster_hidden.vbs" not in text
    for marker in LAUNCHER_HAMSTER_MARKERS:
        assert marker in text
    assert 'set "LIG_AGENTOPS_HOME=%HAMSTER_HOME%"' in text
    assert 'set "PYTHONPATH=%HAMSTER_HOME%;%PYTHONPATH%"' in text
    assert "call \"%AGENTOPS_HOME%\\launch\\_pyw.bat\"" in text
    assert 'start "OpenCodeLIG Hamster" /B /MIN /D "%HAMSTER_HOME%" %PYW% "%HAMSTER_PY%"' in text
    assert 'if defined HAMSTER_PY (' not in text


def test_ocd_wrapper_passes_current_folder_when_no_argument() -> None:
    bat = read(WS / "launch" / "ocd.bat")
    ocd = read(WS / "agent_ops" / "ocd.py")
    hotfix = read(WS / "patches" / "existing_install_hotfix_20260709.py")

    assert "setlocal EnableExtensions" in bat
    assert "if \"%~1\"==\"\" (" in bat
    assert "if not defined LIG_PROJECT_DIR set \"LIG_PROJECT_DIR=%CD%\"" in bat
    assert "set \"LIG_PROJECT_DIR=%CD%\"" not in bat.replace("if not defined LIG_PROJECT_DIR set \"LIG_PROJECT_DIR=%CD%\"", "")
    assert "env.setdefault(\"LIG_PROJECT_DIR\", str(cwd))" in ocd
    assert "if not defined LIG_PROJECT_DIR set \\\"LIG_PROJECT_DIR=%CD%\\\"" in hotfix


def test_launcher_refreshes_all_required_project_plugins() -> None:
    text = read(WS / "RUN_OPENCODE_LIG.bat")

    for plugin in REQUIRED_PLUGIN_FILES:
        assert plugin in text
    assert PLUGIN_SYNC_GLOB in text
    assert "copy /Y" in text


def test_hamster_status_plugin_tracks_current_opencode_events() -> None:
    text = read(WS / ".opencode" / "plugins" / "hamster-status.ts")

    for marker in HAMSTER_EVENT_BRIDGE_MARKERS:
        assert marker in text
    for marker in HAMSTER_LEGACY_MARKERS:
        assert marker not in text
    assert "properties?.status?.type" in text or "properties.status.type" in text


def test_session_autosave_extracts_current_event_properties() -> None:
    text = read(WS / ".opencode" / "plugins" / "session-autosave.ts")

    for marker in AUTOSAVE_REQUIRED_MARKERS:
        assert marker in text
    assert "for (const [key, child] of Object.entries(value))" in text
    assert "execFileSync" not in text


def test_memory_and_handoff_use_installed_agentops_home() -> None:
    memory = read(WS / ".opencode" / "plugins" / "memory-inject.ts")
    handoff = read(WS / ".opencode" / "plugins" / "compaction-handoff.ts")

    assert "process.env.LIG_AGENTOPS_HOME" in memory
    assert "process.env.LIG_AGENTOPS_HOME" in handoff
    assert "session.status" in memory
    assert "execFileSync" not in memory
    assert "execFile(" in memory or "spawn(" in memory
    assert "STARTUP_REFRESH_COOLDOWN_MS" in memory
    assert "COMPACTION_REFRESH_COOLDOWN_MS" in memory
    assert "try {" in handoff
    assert "} catch {" in handoff


def test_pending_check_flags_plugin_runtime_not_just_file_presence() -> None:
    text = read(WS / "agent_ops" / "pending_check.py")

    assert "OpenCode plugin runtime enabled" in text
    assert "OPENCODE_PURE" in text
    assert "OpenCode fast runtime isolation" in text
    assert "direct hamster launcher" in text
    assert "hamster-status.ts" in text
    assert "session-autosave.ts" in text


def test_existing_install_hotfix_contains_same_bridge_repairs() -> None:
    text = read(WS / "patches" / "existing_install_hotfix_20260709.py")

    for marker in [
        "HAMSTER_STATUS_PLUGIN",
        "MEMORY_INJECT_PLUGIN",
        "COMPACTION_HANDOFF_PLUGIN",
        "OPENCODE_PURE",
        PLUGIN_SYNC_GLOB,
        "session.next.text.delta",
        "session.status",
        "from agent_ops.release_contracts import",
    ]:
        assert marker in text


def test_litellm_remote_cost_map_fetch_is_disabled_offline() -> None:
    launcher = read(WS / "RUN_OPENCODE_LIG.bat")
    agentops = read(WS / "agent_ops" / "agentops.py")
    hotfix = read(WS / "patches" / "existing_install_hotfix_20260709.py")

    for text in [launcher, agentops, hotfix]:
        assert "LITELLM_LOCAL_MODEL_COST_MAP" in text
    assert 'set "LITELLM_LOCAL_MODEL_COST_MAP=True"' in launcher
    assert 'os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")' in agentops
    assert "LiteLLM offline" in hotfix


def test_slow_startup_does_not_kill_hamster_or_block_tui() -> None:
    hamster = read(WS / "agent_ops" / "ui" / "hamster_overlay.py")
    launcher = read(WS / "RUN_OPENCODE_LIG.bat")
    memory = read(WS / ".opencode" / "plugins" / "memory-inject.ts")
    hotfix = read(WS / "patches" / "existing_install_hotfix_20260709.py")

    assert "LIG_HAMSTER_START_GRACE_SECONDS" in hamster
    assert "START_GRACE_SECONDS" in hamster
    assert "> START_GRACE_SECONDS" in hamster
    assert 'set "LIG_HAMSTER_START_GRACE_SECONDS=300"' in launcher
    assert "setTimeout" in memory
    assert "refreshStartupRecallAsync" in memory
    assert "patch_hamster_start_grace" in hotfix
    assert "hamster_launcher.log" in hotfix
