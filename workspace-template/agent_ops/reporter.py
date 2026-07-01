# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from .core import REPORTS, LOGS, STATE, read_json, tail_jsonl, atomic_write_text
from .queue_manager import summary as queue_summary
from .state_manager import heartbeat, update_checkpoint

def write_report() -> dict:
    heartbeat("report")
    data = {"run_state": read_json(STATE / "RUN_STATE.json", {}), "checkpoint": read_json(STATE / "CHECKPOINT.json", {}), "active_task": read_json(STATE / "ACTIVE_TASK.json", {}), "queue": queue_summary(), "recent_failures": tail_jsonl(LOGS / "failure_log.jsonl", 10)}
    lines = ["# AgentOps Executive Report", "", "## Summary", "- v3.1 separates OpenCode interactive mode from external orchestrator mode.", "- Long loops must run outside OpenCode bash.", "- Memory source of truth is `.agent-memory/memory.jsonl`.", "- LLM tasks receive recalled lessons/preferences before execution.", "", "## State", "```json", json.dumps(data, ensure_ascii=False, indent=2), "```"]
    atomic_write_text(REPORTS / "EXECUTIVE_REPORT.md", "\n".join(lines))
    update_checkpoint("report generated")
    return data
