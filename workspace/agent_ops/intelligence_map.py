# -*- coding: utf-8 -*-
"""Whole-system intelligence inventory for OpenCodeLIG.

This module is the WS-0 contract from AUTO_ORCHESTRATION_PLAN_20260708.md.
It does not execute tools. It records which intelligence surfaces exist and
whether each one is part of the automatic route, an advanced direct path,
pending validation, or intentionally deprecated.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence


VALID_KINDS = {
    "command",
    "capability",
    "tool",
    "adapter",
    "artifact",
    "context",
    "memory",
    "maintenance",
    "safety",
    "packaging",
}

VALID_STATUS = {"auto", "advanced", "pending", "deprecated"}


@dataclass(frozen=True)
class IntelligenceItem:
    """One declared intelligence surface and its current product role."""

    id: str
    kind: str
    owner_files: Sequence[str]
    status: str
    route: str = ""
    reason: str = ""
    safety: str = ""


def _item(
    kind: str,
    name: str,
    owner_files: Sequence[str],
    status: str,
    route: str = "",
    reason: str = "",
    safety: str = "",
) -> IntelligenceItem:
    return IntelligenceItem(
        id=f"{kind}:{name}",
        kind=kind,
        owner_files=tuple(owner_files),
        status=status,
        route=route,
        reason=reason,
        safety=safety,
    )


def _items(kind: str, names: Iterable[str], owner_file: str, status: str,
           route: str = "", reason: str = "", safety: str = "") -> List[IntelligenceItem]:
    return [_item(kind, name, [owner_file], status, route, reason, safety) for name in names]


COMMAND_ITEMS = [
    _item("command", "auto", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/auto.md"],
          "auto", "auto", "Single automatic entrypoint that routes to command-native/artifact/tool/memory paths.",
          "delegates to existing approval/guard behavior"),
    _item("command", "work", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/work.md"],
          "auto", "artifact_or_agent", "Current high-level work path; WS-1 will place /auto above it.",
          "approval required for --execute"),
    _item("command", "agent", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/agentrun.md"],
          "auto", "tool_agent", "Tool-use execution path selected for app/file/browser tasks.",
          "tool dispatcher risk audit"),
    _item("command", "plan", ["workspace/agent_ops/agentops.py"],
          "advanced", "planning", "CLI-only planning backend; no slash command yet.", "read-only by default"),
    _item("command", "schedule", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/schedule.md"],
          "auto", "command_native:schedule", "Stable command-native route for dates and reminders.",
          "remove requires approval"),
    _item("command", "routine", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/routine.md"],
          "auto", "command_native:routine", "Reusable workflow route; replay remains guarded.",
          "replay passes command guard"),
    _item("command", "recall", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/recall.md"],
          "auto", "memory_wiki", "Recall is automatic context and direct query surface.", "read-only"),
    _item("command", "remember", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/remember.md"],
          "auto", "memory", "Explicit user memory write; protected as user-sourced.", "USERDATA append only"),
    _item("command", "log-activity", ["workspace/agent_ops/agentops.py", "workspace/.opencode/plugins/memory-inject.ts"],
          "advanced", "memory", "Plugin-internal low-priority activity log (TUI compaction summary); no slash command.",
          "USERDATA append only, low priority"),
    _item("command", "wiki", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/wiki.md"],
          "auto", "memory_wiki", "Wiki consolidation/opening supports automatic recall.", "manual notes preserved"),
    _item("command", "book", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/book.md"],
          "auto", "memory_wiki", "Knowledge book is generated from accumulated memory/wiki.", "read/generated output"),
    _item("command", "briefing", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/briefing.md"],
          "auto", "secretary", "Daily assistant summary can be command-native routed.", "read-mostly"),
    _item("command", "weekly", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/weekly.md"],
          "auto", "secretary", "Weekly report is a stable command-native artifact path.", "read-mostly"),
    _item("command", "report-html", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/report-html.md"],
          "auto", "artifact:html_report", "Data/report artifact generation path.", "local file output"),
    _item("command", "report-xlsx", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/report-xlsx.md"],
          "auto", "artifact:xlsx_report", "Spreadsheet report artifact path.", "local file output"),
    _item("command", "office-doc", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/office-doc.md"],
          "auto", "artifact:office_doc", "Real docx/pptx generation path when deps/apps exist.", "local file output"),
    _item("command", "doc-template", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/doc-template.md"],
          "auto", "artifact:doc_template", "Structured document template path.", "local file output"),
    _item("command", "ocr", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/ocr.md"],
          "auto", "tool_agent:ocr", "Screen/file OCR should be exposed automatically when requested.",
          "engine/app availability may be pending"),
    _item("command", "deps", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/deps.md"],
          "advanced", "diagnostics", "Dependency inspection is an advanced diagnostic command.", "read-only"),
    _item("command", "doctor", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/doctor.md"],
          "advanced", "diagnostics", "Health diagnosis used by verification and troubleshooting.", "read-only"),
    _item("command", "verify", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/verify.md"],
          "advanced", "verification", "Explicit verification command; auto hooks will call equivalent checks.", "read-only"),
    _item("command", "status", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/status.md"],
          "advanced", "diagnostics", "Status display for operator/user visibility.", "read-only"),
    _item("command", "report", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/report.md"],
          "advanced", "diagnostics", "Operational report command for handoff/debugging.", "read-only"),
    _item("command", "timeline", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/timeline.md"],
          "advanced", "diagnostics", "Timeline/audit inspection; WS-6 may feed error patterns from it.", "read-only"),
    _item("command", "watch", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/watch.md"],
          "advanced", "maintenance", "Long-wait monitor is an operator tool, not default route.", "read-only monitor"),
    _item("command", "checkpoint", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/checkpoint.md"],
          "advanced", "state", "Manual progress marker for handoff continuity.", "state append"),
    _item("command", "resume", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/resume.md"],
          "advanced", "state", "Session continuity aid; not task execution.", "read-only/state"),
    _item("command", "continue-once", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/continue.md"],
          "advanced", "orchestrator", "Queue worker primitive; not user default.", "queue guarded"),
    _item("command", "enqueue", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/enqueue.md"],
          "advanced", "orchestrator", "Manual queue insertion for supervisors.", "queue append"),
    _item("command", "orchestrator", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/orchestrator.md"],
          "advanced", "orchestrator", "Continuous runner requires operator intent.", "stop/queue guards"),
    _item("command", "stop", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/agentstop.md"],
          "advanced", "orchestrator", "Stop signal for autonomous loops.", "safe stop only"),
    _item("command", "unstop", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/unstop.md"],
          "advanced", "orchestrator", "Resume signal for autonomous loops.", "operator intent required"),
    _item("command", "safety-check", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/permission.md"],
          "advanced", "safety", "Explicit safety classifier for operator review.", "read-only classification"),
    _item("command", "safe-write", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/safecreate.md"],
          "advanced", "safety", "Guarded write helper, not hidden automatic overwrite.", "safe writer"),
    _item("command", "fix", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/fix.md"],
          "advanced", "selfheal", "Repair helper needs operator/reviewer context.", "review required"),
    _item("command", "selfheal", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/selfheal.md"],
          "advanced", "selfheal", "Self-heal plan generation is diagnostic/repair support.", "plan before action"),
    _item("command", "dashboard", ["workspace/agent_ops/agentops.py"],
          "advanced", "diagnostics", "CLI command without slash surface; diagnostic display.", "read-only"),
    _item("command", "log-failure", ["workspace/agent_ops/agentops.py"],
          "advanced", "memory:error", "Internal/manual failure logging primitive.", "append only"),
    _item("command", "memorycheck", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/memorycheck.md"],
          "advanced", "memory", "Memory health diagnostic.", "read-only"),
    _item("command", "init", ["workspace/agent_ops/agentops.py", "workspace/.opencode/commands/start.md"],
          "advanced", "setup", "Initialization should be explicit.", "workspace setup"),
    _item("command", "agentmode", ["workspace/.opencode/commands/agentmode.md"],
          "advanced", "tui_mode", "OpenCode-side mode helper; not an agentops CLI command.", "operator intent"),
    _item("command", "autopilot", ["workspace/.opencode/commands/autopilot.md"],
          "advanced", "tui_mode", "OpenCode-side autonomous mode helper; operator-controlled.", "operator intent"),
    _item("command", "compactprep", ["workspace/.opencode/commands/compactprep.md"],
          "advanced", "tui_memory", "Compaction preparation helper; plugin/TUI concern.", "state summary only"),
    _item("command", "lintcmd", ["workspace/.opencode/commands/lintcmd.md"],
          "advanced", "diagnostics", "Command lint helper, not default route.", "read-only"),
]


CAPABILITY_ITEMS = _items(
    "capability",
    [
        "file_ops",
        "document_generation",
        "macro_generation",
        "spreadsheet_generation",
        "presentation_generation",
        "browser_automation",
        "web_mail_assistant",
        "schedule_management",
        "meeting_minutes",
        "weekly_report",
        "matlab_automation",
        "simulation_automation",
        "office_cad_automation",
    ],
    "workspace/agent_ops/capabilities.py",
    "auto",
    "capability_router",
    "Primary request classification vocabulary.",
)


ARTIFACT_ITEMS = [
    _item("artifact", "vba_macro", ["workspace/agent_ops/artifact_generators.py", "workspace/agent_ops/capabilities.py"],
          "auto", "artifact:vba_macro", "Macro scaffold artifact generated from multiple capabilities.",
          "app execution requires target app/approval"),
    _item("artifact", "document", ["workspace/agent_ops/artifact_generators.py", "workspace/agent_ops/capabilities.py"],
          "auto", "artifact:document", "Default report/document artifact.", "local file output"),
    _item("artifact", "slide_outline", ["workspace/agent_ops/artifact_generators.py", "workspace/agent_ops/capabilities.py"],
          "auto", "artifact:slide_outline", "Presentation outline/spec artifact.", "pptx generation may require deps/app"),
    _item("artifact", "browser_script", ["workspace/agent_ops/artifact_generators.py", "workspace/agent_ops/capabilities.py"],
          "auto", "artifact:browser_script", "Browser automation scaffold artifact.", "real site login is company pending"),
    _item("artifact", "mail_report", ["workspace/agent_ops/artifact_generators.py", "workspace/agent_ops/capabilities.py"],
          "auto", "artifact:mail_report", "Mail triage/report artifact.", "real mailbox validation pending"),
    _item("artifact", "matlab_script", ["workspace/agent_ops/artifact_generators.py", "workspace/agent_ops/capabilities.py"],
          "auto", "artifact:matlab_script", "MATLAB post-processing script artifact.", "script execution"),
    _item("artifact", "autocad_script", ["workspace/agent_ops/artifact_generators.py", "workspace/agent_ops/capabilities.py"],
          "auto", "artifact:autocad_script", "AutoCAD script artifact.", "requires user-provided .dwg for execution"),
    _item("artifact", "fluent_journal", ["workspace/agent_ops/artifact_generators.py", "workspace/agent_ops/capabilities.py"],
          "pending", "artifact:fluent_journal", "Fluent journal artifact exists but execution validation remains pending.",
          "app validation"),
    _item("artifact", "ansys_script", ["workspace/agent_ops/artifact_generators.py", "workspace/agent_ops/capabilities.py"],
          "advanced", "artifact:ansys_script", "ANSYS GUI script is manual/advanced until adapter execution is proven.",
          "manual app validation"),
    _item("artifact", "meeting_minutes", ["workspace/agent_ops/artifact_generators.py", "workspace/agent_ops/capabilities.py"],
          "auto", "artifact:meeting_minutes", "Meeting-minutes artifact with schedule suggestions.", "does not auto-register schedule"),
]


TOOL_ITEMS = [
    *_items("tool", ["read_file", "list_dir", "search_files", "run_diagnostic"],
            "workspace/agent_ops/tool_dispatch.py", "auto", "tool_agent:file_ops",
            "Read/diagnostic tools are safe default tool-agent surfaces.", "read-only"),
    *_items("tool", ["write_file", "append_file", "replace_in_file"],
            "workspace/agent_ops/tool_dispatch.py", "auto", "tool_agent:file_ops",
            "Write tools are available to the tool agent but stay path-guarded.", "path guarded"),
    *_items("tool", ["browse_tabs", "read_web_page", "browser_action", "new_tab", "snapshot",
                     "find_clickables", "click", "screenshot", "wait_for_selector", "select_tab", "spa_map"],
            "workspace/agent_ops/tool_dispatch.py", "auto", "tool_agent:browser",
            "Browser tools are selected for web/app UI tasks.", "debug Chrome required"),
    *_items("tool", ["project_info"], "workspace/agent_ops/tool_dispatch.py", "auto",
            "context", "Context introspection tool.", "read-only"),
    *_items("tool", ["remember"], "workspace/agent_ops/tool_dispatch.py", "auto",
            "memory", "Agent lesson capture tool.", "USERDATA append only"),
    *_items("tool", ["excel_app", "outlook_app", "hwp_app", "solidworks_app", "ocr_screen",
                     "desktop_ui", "matlab_run", "fluent_run", "autocad_run"],
            "workspace/agent_ops/tool_dispatch.py", "auto", "tool_agent:app_adapter",
            "App execution tools are exposed by request and fail gracefully when unavailable.",
            "adapter availability and approval/risk checks"),
]


ADAPTER_ITEMS = [
    _item("adapter", "solidworks", ["workspace/agent_ops/adapters/solidworks_com.py", "workspace/agent_ops/adapters/__init__.py"],
          "pending", "tool_agent:solidworks_app", "COM connection exists but macro execution remains app validation pending.", "app validation"),
    _item("adapter", "office", ["workspace/agent_ops/adapters/excel_com.py", "workspace/agent_ops/adapters/office_convert.py", "workspace/agent_ops/adapters/__init__.py"],
          "auto", "tool_agent:excel_app", "Office adapter is validated for Excel and used for Office document workflows.", "copy/write guarded"),
    _item("adapter", "outlook", ["workspace/agent_ops/adapters/outlook_com.py", "workspace/agent_ops/adapters/__init__.py"],
          "auto", "tool_agent:outlook_app", "Outlook read/calendar paths are validated; writes remain guarded.", "send/write guarded"),
    _item("adapter", "browser", ["workspace/agent_ops/adapters/browser_cdp.py", "workspace/agent_ops/adapters/ws_min.py", "workspace/agent_ops/adapters/__init__.py"],
          "auto", "tool_agent:browser", "Chrome CDP adapter and local ws helper power browser automation.", "local debug Chrome only"),
    _item("adapter", "matlab", ["workspace/agent_ops/adapters/matlab_batch.py", "workspace/agent_ops/adapters/__init__.py"],
          "auto", "tool_agent:matlab_run", "MATLAB batch path has company validation evidence.", "script execution"),
    _item("adapter", "autocad", ["workspace/agent_ops/adapters/autocad_batch.py", "workspace/agent_ops/adapters/__init__.py"],
          "auto", "tool_agent:autocad_run", "AutoCAD batch path has company validation evidence.", "runs on copied drawing"),
    _item("adapter", "fluent", ["workspace/agent_ops/adapters/fluent_batch.py", "workspace/agent_ops/adapters/__init__.py"],
          "pending", "tool_agent:fluent_run", "ANSYS Fluent execution still needs app validation.", "app validation"),
    _item("adapter", "hwp", ["workspace/agent_ops/adapters/hwp_com.py", "workspace/agent_ops/adapters/__init__.py"],
          "auto", "tool_agent:hwp_app", "HWP document generation/convert path has validation evidence.", "local file output"),
    _item("adapter", "ocr_screen", ["workspace/agent_ops/adapters/ocr_screen.py", "workspace/agent_ops/adapters/__init__.py"],
          "pending", "tool_agent:ocr_screen", "OCR engine import/validation is pending.", "optional engine"),
    _item("adapter", "desktop_ui", ["workspace/agent_ops/adapters/desktop_ui.py", "workspace/agent_ops/adapters/__init__.py"],
          "pending", "tool_agent:desktop_ui", "Generic UI automation requires windows-use and target-app validation.", "app validation"),
]


CONTEXT_ITEMS = [
    *_items("context", ["input_ingest", "api_reference", "knowledge_base", "design_guidance",
                        "domain_context", "skill_router", "project_profile"],
            "workspace/agent_ops", "auto", "context_injection",
            "Automatic prompt/context enrichment surface.", "read-only/context budget"),
    *_items("context", ["artifact_generators", "artifact_quality", "html_report",
                        "office_writer", "doc_templates", "reporter"],
            "workspace/agent_ops", "auto", "artifact_generation",
            "Artifact generation and validation intelligence.", "local file output"),
]


MEMORY_ITEMS = [
    _item("memory", "memory_manager", ["workspace/agent_ops/memory_manager.py"],
          "auto", "memory", "Primary memory append/recall path.", "USERDATA append/lock"),
    _item("memory", "wiki_manager", ["workspace/agent_ops/wiki_manager.py"],
          "auto", "memory_wiki", "Consolidates memory into recallable wiki pages.", "manual wiki preserved"),
    _item("memory", "wiki_vault", ["workspace/agent_ops/wiki_vault.py"],
          "auto", "memory_wiki", "Obsidian vault seeding/opening helper.", "no overwrite of manual notes"),
    _item("memory", "knowledge_book", ["workspace/agent_ops/knowledge_book.py"],
          "auto", "memory_wiki", "Generated knowledge book from memory/wiki/audit.", "generated output"),
]


MAINTENANCE_ITEMS = [
    _item("maintenance", "auto_maintain", ["workspace/agent_ops/auto_maintain.py"],
          "auto", "maintenance", "Throttled memory/wiki/book maintenance.", "protected user memories"),
    _item("maintenance", "activity_timeline", ["workspace/agent_ops/activity_timeline.py"],
          "advanced", "diagnostics", "Timeline inspection feeds future error-pattern promotion.", "read-only"),
    _item("maintenance", "status_writer", ["workspace/agent_ops/status_writer.py"],
          "auto", "status", "Live status/event publishing for user visibility.", "best-effort"),
    _item("maintenance", "secretary", ["workspace/agent_ops/secretary.py"],
          "auto", "secretary", "Briefing/weekly intelligence.", "read-mostly"),
    _item("maintenance", "queue_orchestrator", ["workspace/agent_ops/queue_manager.py", "workspace/agent_ops/orchestrator.py"],
          "advanced", "orchestrator", "Queue execution is powerful and remains operator-controlled.", "stop/claim guards"),
    _item("maintenance", "routines", ["workspace/agent_ops/routines.py"],
          "auto", "routine", "Record/replay capability for repeated work.", "replay guarded"),
    _item("maintenance", "schedule_store", ["workspace/agent_ops/schedule_store.py"],
          "auto", "schedule", "Persistent local schedule intelligence.", "remove guarded"),
    _item("maintenance", "state_manager", ["workspace/agent_ops/state_manager.py"],
          "auto", "state", "Session checkpoint/done/blocker state used by resume and orchestrator.", "state append"),
    _item("maintenance", "clean_stale", ["workspace/agent_ops/clean_stale.py"],
          "advanced", "maintenance", "Explicit stale-file cleanup helper; not automatic default.", "destructive cleanup requires care"),
]


SAFETY_ITEMS = [
    _item("safety", "approval", ["workspace/agent_ops/approval.py"],
          "auto", "safety", "Current-session approval gate.", "cannot be bypassed"),
    _item("safety", "command_guard", ["workspace/agent_ops/command_guard.py", "workspace/agent_ops/COMMAND_GUARD_RULES.md"],
          "auto", "safety", "Dangerous command and approval-window corruption guard.", "cannot be bypassed"),
    _item("safety", "safety", ["workspace/agent_ops/safety.py"],
          "auto", "safety", "Action classifier and safety decision log.", "cannot be bypassed"),
    _item("safety", "audit", ["workspace/agent_ops/audit.py"],
          "auto", "audit", "Append-only audit trail for tools/actions.", "diagnostics only"),
    _item("safety", "safe_file_writer", ["workspace/agent_ops/safe_file_writer.py"],
          "advanced", "safety", "Explicit safe write helper.", "path guarded"),
]


PACKAGING_ITEMS = [
    _item("packaging", "offline_installer", ["INSTALL_OFFLINE_LIG_OPENCODE.bat.txt", "SHA256SUMS.txt"],
          "advanced", "packaging", "Offline installer is distribution-time, not runtime auto route.", "CRLF/SHA256"),
    _item("packaging", "payload_opencode", ["payload/opencode.exe"],
          "advanced", "packaging", "Bundled OpenCode binary for offline deployment.", "checksum verified"),
    _item("packaging", "launch_bats", ["workspace/launch", "workspace/RUN_OPENCODE_LIG.bat"],
          "advanced", "runtime", "Launchers set UTF-8/env and start TUI.", "CRLF and env integrity"),
    _item("packaging", "opencode_config", ["workspace/opencode.json", "workspace/config/lig-api.env.example"],
          "advanced", "runtime_config", "Runtime provider/config surface; model defaults require user approval.",
          "LLM settings immutable without approval"),
    _item("packaging", "tools_dropzone", ["workspace/tools"],
          "pending", "offline_tools", "Optional offline binaries/wheels drop zone.", "manual import required"),
]


INTELLIGENCE_ITEMS: List[IntelligenceItem] = [
    *COMMAND_ITEMS,
    *CAPABILITY_ITEMS,
    *ARTIFACT_ITEMS,
    *TOOL_ITEMS,
    *ADAPTER_ITEMS,
    *CONTEXT_ITEMS,
    *MEMORY_ITEMS,
    *MAINTENANCE_ITEMS,
    *SAFETY_ITEMS,
    *PACKAGING_ITEMS,
]


def all_items() -> List[IntelligenceItem]:
    return list(INTELLIGENCE_ITEMS)


def by_id() -> Dict[str, IntelligenceItem]:
    return {item.id: item for item in INTELLIGENCE_ITEMS}


def ids_for_kind(kind: str) -> set[str]:
    return {item.id for item in INTELLIGENCE_ITEMS if item.kind == kind}


def coverage_summary() -> Dict[str, Dict[str, int]]:
    summary: Dict[str, Dict[str, int]] = {}
    for item in INTELLIGENCE_ITEMS:
        bucket = summary.setdefault(item.kind, {})
        bucket[item.status] = bucket.get(item.status, 0) + 1
    return summary


def validate_items(items: Iterable[IntelligenceItem] | None = None) -> List[str]:
    """Return human-readable map contract violations."""
    rows = list(items if items is not None else INTELLIGENCE_ITEMS)
    errors: List[str] = []
    seen: set[str] = set()
    for item in rows:
        if item.id in seen:
            errors.append(f"duplicate id: {item.id}")
        seen.add(item.id)
        if item.kind not in VALID_KINDS:
            errors.append(f"{item.id}: invalid kind {item.kind}")
        if item.status not in VALID_STATUS:
            errors.append(f"{item.id}: invalid status {item.status}")
        if not item.owner_files:
            errors.append(f"{item.id}: owner_files is empty")
        if item.status in {"advanced", "pending", "deprecated"} and not item.reason:
            errors.append(f"{item.id}: {item.status} item needs reason")
        if item.status == "auto" and not item.route:
            errors.append(f"{item.id}: auto item needs route")
    return errors
