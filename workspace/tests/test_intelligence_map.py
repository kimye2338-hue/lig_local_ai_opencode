# -*- coding: utf-8 -*-
"""WS-0 intelligence-map coverage tests.

Run: py -3.11 tests\test_intelligence_map.py
"""
from __future__ import annotations

import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

from agent_ops.capabilities import CAPABILITIES, ARTIFACT_KIND_INFO  # noqa: E402
from agent_ops.tool_dispatch import REGISTRY  # noqa: E402
from agent_ops.adapters import ADAPTERS  # noqa: E402
from agent_ops.intelligence_map import (  # noqa: E402
    all_items,
    by_id,
    coverage_summary,
    ids_for_kind,
    validate_items,
)

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def main() -> None:
    items = all_items()
    item_by_id = by_id()
    check("map has items", bool(items))
    check("map ids are unique", len(item_by_id) == len(items))
    errors = validate_items(items)
    check("map schema/status/reason contract is valid", not errors, "\n".join(errors[:20]))

    actual_commands = {p.stem for p in (WS / ".opencode" / "commands").glob("*.md")}
    command_aliases = {
        "agentrun": "agent",
        "agentstop": "stop",
        "continue": "continue-once",
        "permission": "safety-check",
        "safecreate": "safe-write",
        "start": "init",
    }
    expected_command_ids = {f"command:{command_aliases.get(name, name)}" for name in actual_commands}
    missing_commands = expected_command_ids - set(item_by_id)
    check("all .opencode slash commands are mapped", not missing_commands,
          str(sorted(missing_commands)))

    cli_commands = {
        "init", "status", "fix", "dashboard", "resume", "watch", "report-html",
        "timeline", "deps", "report-xlsx", "office-doc", "routine", "ocr",
        "doc-template", "checkpoint", "doctor", "verify", "report", "selfheal",
        "log-failure", "memorycheck", "remember", "recall", "enqueue",
        "continue-once", "orchestrator", "stop", "unstop", "agent", "plan",
        "work", "schedule", "briefing", "weekly", "book", "wiki",
        "safety-check", "safe-write",
    }
    missing_cli = {f"command:{name}" for name in cli_commands} - set(item_by_id)
    check("all agentops CLI commands are mapped", not missing_cli,
          str(sorted(missing_cli)))

    missing_caps = {f"capability:{name}" for name in CAPABILITIES} - set(item_by_id)
    check("all capability ids are mapped", not missing_caps,
          str(sorted(missing_caps)))

    declared_artifacts = {
        kind
        for spec in CAPABILITIES.values()
        for kind in spec.get("artifact_kinds", [])
    } | set(ARTIFACT_KIND_INFO)
    missing_artifacts = {f"artifact:{name}" for name in declared_artifacts} - set(item_by_id)
    check("all artifact kinds are mapped", not missing_artifacts,
          str(sorted(missing_artifacts)))

    missing_tools = {f"tool:{name}" for name in REGISTRY} - set(item_by_id)
    check("all tool_dispatch REGISTRY tools are mapped", not missing_tools,
          str(sorted(missing_tools)))

    missing_adapters = {f"adapter:{name}" for name in ADAPTERS} - set(item_by_id)
    check("all declared adapters are mapped", not missing_adapters,
          str(sorted(missing_adapters)))

    adapter_owner_files = {
        Path(owner).name
        for item in items
        if item.kind == "adapter"
        for owner in item.owner_files
    }
    actual_adapter_files = {
        p.name for p in (WS / "agent_ops" / "adapters").glob("*.py")
        if p.name != "__init__.py"
    }
    missing_adapter_files = actual_adapter_files - adapter_owner_files
    check("all adapter implementation files are owned by a mapped adapter",
          not missing_adapter_files, str(sorted(missing_adapter_files)))

    for required_kind in [
        "command", "capability", "artifact", "tool", "adapter", "context",
        "memory", "maintenance", "safety", "packaging",
    ]:
        check(f"{required_kind} kind has at least one item",
              bool(ids_for_kind(required_kind)))

    for item in items:
        if item.status == "auto":
            check(f"{item.id} auto item has route", bool(item.route))
        if item.status in {"advanced", "pending", "deprecated"}:
            check(f"{item.id} non-auto item has reason", bool(item.reason))

    summary = coverage_summary()
    check("coverage summary counts every item",
          sum(sum(v.values()) for v in summary.values()) == len(items),
          str(summary))
    check("map records pending items honestly",
          any(item.status == "pending" for item in items))

    print(f"\nALL {PASS} CHECKS PASSED (intelligence map)")


if __name__ == "__main__":
    main()
