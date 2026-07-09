# -*- coding: utf-8 -*-
"""Shared release/runtime contracts for OpenCodeLIG.

Keep launcher/plugin/static verification markers in one place so pending checks,
quality gate, tests, and hotfix regeneration do not drift.
"""
from __future__ import annotations

PLUGIN_SYNC_GLOB = ".opencode\\plugins\\*.ts"

REQUIRED_PLUGIN_FILES = (
    "command-guard.ts",
    "compaction-handoff.ts",
    "hamster-status.ts",
    "memory-inject.ts",
    "session-autosave.ts",
)

LAUNCHER_FAST_RUNTIME_MARKERS = (
    "OPENCODE_FAST_BASE=%OPENCODE_USERDATA%\\opencode_fast_runtime",
    "OPENCODE_CONFIG_DIR=%OPENCODE_FAST_CONFIG%",
    "XDG_CONFIG_HOME=%OPENCODE_FAST_CONFIG%",
    "XDG_DATA_HOME=%OPENCODE_FAST_DATA%",
    "XDG_CACHE_HOME=%OPENCODE_FAST_CACHE%",
    "OPENCODE_DISABLE_MODELS_FETCH=1",
    "OPENCODE_DISABLE_AUTOUPDATE=1",
    "OPENCODE_DISABLE_LSP_DOWNLOAD=1",
    "OPENCODE_MODELS_URL=http://127.0.0.1:9/api.json",
    "NPM_CONFIG_REGISTRY=http://127.0.0.1:9/",
    "BUN_CONFIG_REGISTRY=http://127.0.0.1:9/",
    "NO_PROXY=*",
    'set "OPENCODE_PURE="',
)

LAUNCHER_HAMSTER_MARKERS = (
    "LIG_WORKSPACE_HOME=%USERPROFILE%\\OpenCodeLIG\\workspace",
    "agent_ops\\ui\\hamster_overlay.py",
    "hamster_overlay_start.log",
    'start "OpenCodeLIG Hamster"',
    "LIG_AGENTOPS_HOME=%LIG_WORKSPACE_HOME%",
)

LAUNCHER_PROJECT_DIR_MARKERS = (
    "if not defined LIG_PROJECT_DIR (",
    'set "LIG_PROJECT_DIR=%CD%"',
    "%WINDIR%\\System32",
    "%WINDIR%\\SysWOW64",
    'cd /d "%LIG_PROJECT_DIR%"',
)

LAUNCHER_DRIVE_ROOT_FALLBACK = (
    'for %%I in ("%LIG_PROJECT_DIR%") do if /I "%%~fI"=="%%~dI\\\\" '
    'set "LIG_PROJECT_DIR=%AGENTOPS_HOME%"'
)

HAMSTER_EVENT_BRIDGE_MARKERS = (
    "session.status",
    "session.next.text.delta",
    "session.next.step.started",
    "session.next.step.ended",
    "session.next.step.failed",
    "session.next.tool.called",
    "session.next.tool.success",
    "session.next.tool.failed",
    "experimental.session.compacting",
    'properties?.tool === "task"',
    "isTaskToolCall",
    "isTaskToolSuccess",
    "isTaskToolFailure",
    "writeAtomic",
    "opencode-event-types.log",
)

HAMSTER_LEGACY_MARKERS = (
    'type === "task.start"',
    'type === "task.end"',
    'type === "session.task.started"',
    'type === "session.next.task.started"',
    "event?.properties?.agent_name",
    'body.includes("subagent")',
    'body.includes("agent_name")',
)

AUTOSAVE_REQUIRED_MARKERS = (
    'appendFileSync(sessionFile()',
    '"properties"',
    '"delta"',
    '"input"',
    '"output"',
    "Object.entries(value)",
    "log-activity",
    "rememberSessionActivity",
    "bufferEventText",
    "takeBufferedText",
    "session.status",
    "session.next.text.delta",
    "session.next.step.ended",
    "session.next.step.failed",
    "token",
    "secret",
    "credential",
)

MEMORY_INJECT_REQUIRED_MARKERS = (
    "fallbackStartupBlock",
    "refreshStartupRecallAsync",
    "setTimeout",
    "process.env.LIG_AGENTOPS_HOME",
    "session.status",
    "STARTUP_REFRESH_COOLDOWN_MS",
    "COMPACTION_REFRESH_COOLDOWN_MS",
    "IDLE_REFRESH_COOLDOWN_MS",
    "cachedRecallBlock",
)
