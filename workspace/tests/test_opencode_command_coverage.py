# -*- coding: utf-8 -*-
"""OpenCode slash command coverage for user-facing AgentOps features.

Run: py -3.11 tests\test_opencode_command_coverage.py
"""
from __future__ import annotations

import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
COMMANDS = WS / ".opencode" / "commands"
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
    required = {
        "auto", "work", "schedule", "briefing", "weekly", "remember", "recall",
        "doctor", "verify", "status", "report", "resume", "checkpoint",
        "deps", "ocr", "routine", "report-html", "report-xlsx",
        "office-doc", "doc-template", "book", "wiki", "timeline", "watch",
    }
    names = {p.stem for p in COMMANDS.glob("*.md")}
    check("user-facing CLI features have slash commands",
          required <= names, str(sorted(required - names)))
    for name in sorted(required):
        text = (COMMANDS / f"{name}.md").read_text(encoding="utf-8")
        check(f"{name} command delegates to agentops",
              "agent_ops/agentops.py" in text or "agent_ops\\agentops.py" in text,
              text[:160])

    print(f"\nALL {PASS} CHECKS PASSED (opencode command coverage)")


if __name__ == "__main__":
    main()
