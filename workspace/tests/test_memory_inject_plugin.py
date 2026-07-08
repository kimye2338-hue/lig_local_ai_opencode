# -*- coding: utf-8 -*-
"""OpenCode memory injection plugin structure checks.

Run: py -3.11 tests\test_memory_inject_plugin.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
PLUGIN = WS / ".opencode" / "plugins" / "memory-inject.ts"
START = WS / ".opencode" / "commands" / "start.md"
AGENT = WS / ".opencode" / "agents" / "agent.md"
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
    text = PLUGIN.read_text(encoding="utf-8")
    start = START.read_text(encoding="utf-8")
    agent = AGENT.read_text(encoding="utf-8")

    check("memory plugin exists", PLUGIN.exists())
    check("plugin is node-parseable JS syntax",
          subprocess.run(["node", "--check", str(PLUGIN)], cwd=WS).returncode == 0)
    check("plugin prefers AGENTOPS_HOME", "process.env.AGENTOPS_HOME" in text)
    check("plugin calls recall pinned", '["recall", "--pinned"]' in text)
    check("plugin writes SESSION_RECALL fallback", "SESSION_RECALL.md" in text)
    check("plugin injects during compaction", "experimental.session.compacting" in text and "pushContext" in text)
    check("plugin records compaction summaries via remember", '["remember", text, "--title", "OpenCode TUI session"]' in text)
    check("/start runs recall pinned first", "python agent_ops/agentops.py recall --pinned" in start)
    check("agent instructions mention SESSION_RECALL fallback", "SESSION_RECALL.md" in agent)
    check("agent instructions ask to remember useful lesson", "agentops.py remember" in agent)

    print(f"\nALL {PASS} CHECKS PASSED (memory inject plugin)")


if __name__ == "__main__":
    main()
