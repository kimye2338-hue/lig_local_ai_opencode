# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as _dt
import json
import uuid
from typing import Any, Dict, Optional

from .core import STATE, LOGS, ROOT, now, ensure_dirs, atomic_write_json, read_json, atomic_write_text, read_text, append_jsonl, is_stop_requested

def init_state() -> Dict[str, Any]:
    ensure_dirs()
    interruption = detect_interruption()
    if not (STATE / "CURRENT_GOAL.md").exists():
        atomic_write_text(STATE / "CURRENT_GOAL.md", "# Current Goal\n\nContinue project work until the user explicitly stops.\n")
    if not (STATE / "RUN_STATE.json").exists():
        atomic_write_json(STATE / "RUN_STATE.json", {
            "run_id": "run_" + uuid.uuid4().hex[:12],
            "created_at": now(),
            "status": "initialized",
            "cwd": str(ROOT),
            "last_heartbeat": now(),
        })
    for name, content in [
        ("ACTIVE_TASK.json", {}),
        ("CHECKPOINT.json", {}),
        ("LAST_KNOWN_GOOD.json", {}),
    ]:
        p = STATE / name
        if not p.exists():
            atomic_write_json(p, content)
    for name, content in [
        ("BLOCKERS.md", "# Blockers\n\n"),
        ("DONE_LOG.md", "# Done Log\n\n"),
    ]:
        p = STATE / name
        if not p.exists():
            atomic_write_text(p, content)
    if interruption.get("interrupted"):
        consume_interruption(interruption)
    update_checkpoint("initial state ensured")
    return interruption

def heartbeat(status: str = "running") -> None:
    ensure_dirs()
    state = read_json(STATE / "RUN_STATE.json", {})
    if not isinstance(state, dict):
        state = {}
    state.setdefault("run_id", "run_" + uuid.uuid4().hex[:12])
    state.update({
        "status": status,
        "last_heartbeat": now(),
        "cwd": str(ROOT),
        "stop_file_exists": is_stop_requested(),
    })
    atomic_write_json(STATE / "RUN_STATE.json", state)
    atomic_write_json(STATE / "HEARTBEAT.json", {
        "timestamp": now(),
        "status": status,
        "stop_file_exists": is_stop_requested(),
    })

def detect_interruption(max_age_seconds: int = 600) -> Dict[str, Any]:
    state = read_json(STATE / "RUN_STATE.json", {})
    result = {"interrupted": False, "reason": None, "run_state": state}
    if not isinstance(state, dict):
        return result
    status = state.get("status")
    last = state.get("last_heartbeat")
    if status in {"continuous", "continuous_external", "continuous_parallel", "running", "active", "orchestrator_once", "checkpoint"} and last:
        try:
            t = _dt.datetime.fromisoformat(str(last))
            age = (_dt.datetime.now(t.tzinfo) - t).total_seconds()
            if age > max_age_seconds:
                result["interrupted"] = True
                result["reason"] = f"stale heartbeat {age:.0f}s"
        except Exception:
            result["interrupted"] = True
            result["reason"] = "cannot parse heartbeat"
    return result

def consume_interruption(interruption: Dict[str, Any]) -> None:
    if not interruption.get("interrupted"):
        return
    active = get_active_task()
    if active.get("status") == "active":
        active["status"] = "pending"
        active["interrupted_recovered_at"] = now()
        active["blocked_reason"] = active.get("blocked_reason") or "Recovered from interrupted run; task returned to pending."
        set_active_task(active)
        try:
            from .queue_manager import update_task
            update_task(active.get("task_id"), status="pending", blocked_reason=active["blocked_reason"])
        except Exception:
            pass
    checkpoint = read_json(STATE / "CHECKPOINT.json", {})
    if not isinstance(checkpoint, dict):
        checkpoint = {}
    checkpoint["interrupted"] = True
    checkpoint["interruption_reason"] = interruption.get("reason")
    checkpoint["interruption_detected_at"] = now()
    atomic_write_json(STATE / "CHECKPOINT.json", checkpoint)
    append_blocker(f"Interrupted run detected and recovered: {interruption.get('reason')}")

def set_active_task(task: Dict[str, Any]) -> None:
    task = dict(task or {})
    if task:
        task["updated_at"] = now()
    atomic_write_json(STATE / "ACTIVE_TASK.json", task)

def get_active_task() -> Dict[str, Any]:
    task = read_json(STATE / "ACTIVE_TASK.json", {})
    return task if isinstance(task, dict) else {}

def update_checkpoint(note: str = "", active_task: Optional[Dict[str, Any]] = None, next_step_status: str = "planned") -> None:
    ensure_dirs()
    if active_task is None:
        active_task = get_active_task()
    current = read_json(STATE / "CHECKPOINT.json", {})
    if not isinstance(current, dict):
        current = {}
    current.update({
        "checkpoint_id": current.get("checkpoint_id") or ("ckpt_" + uuid.uuid4().hex[:10]),
        "updated_at": now(),
        "cwd": str(ROOT),
        "note": note,
        "active_task_id": active_task.get("task_id"),
        "active_task_summary": {
            "task_id": active_task.get("task_id"),
            "status": active_task.get("status"),
            "title": active_task.get("title"),
            "kind": active_task.get("kind"),
            "owner_agent": active_task.get("owner_agent"),
            "risk": active_task.get("risk"),
            "attempt_count": active_task.get("attempt_count"),
        } if active_task else {},
        "next_step_status": next_step_status,
        "stop_file_exists": is_stop_requested(),
    })
    atomic_write_json(STATE / "CHECKPOINT.json", current)
    update_resume_plan(note)
    update_compact_handoff(note)
    heartbeat("checkpoint")

def mark_last_known_good(note: str = "") -> None:
    checkpoint = read_json(STATE / "CHECKPOINT.json", {})
    atomic_write_json(STATE / "LAST_KNOWN_GOOD.json", {
        "timestamp": now(),
        "note": note,
        "checkpoint": checkpoint,
    })

def update_resume_plan(note: str = "") -> None:
    goal = read_text(STATE / "CURRENT_GOAL.md").strip() or "# Current Goal\n\nContinue current work."
    active = get_active_task()
    checkpoint = read_json(STATE / "CHECKPOINT.json", {})
    blockers = read_text(STATE / "BLOCKERS.md").strip()
    interruption_warning = ""
    if isinstance(checkpoint, dict) and checkpoint.get("interrupted"):
        interruption_warning = "\n## INTERRUPTED RUN RECOVERED\n\nPrevious run appears to have been interrupted. Active task was returned to pending if needed. Verify state before continuing.\n"
    text = "\n".join([
        "# Resume Plan",
        "",
        f"- Updated: {now()}",
        f"- Project root: `{ROOT}`",
        f"- Stop requested: `{is_stop_requested()}`",
        interruption_warning,
        "## Current goal",
        goal,
        "",
        "## Active task",
        "```json",
        json.dumps(active, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Checkpoint",
        "```json",
        json.dumps(checkpoint, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Important distinction",
        "- `next_step` and queue items are planned, not approved.",
        "- Risky actions require explicit user approval in the current session.",
        "",
        "## Last note",
        note or "No note.",
        "",
        "## Blockers",
        blockers or "No blockers recorded.",
        "",
        "## Required next behavior",
        "1. Read this file after restart or compaction.",
        "2. Read `ACTIVE_TASK.json`, `CHECKPOINT.json`, and `COMPACT_HANDOFF.md`.",
        "3. Run `/status`, then `/continue` for one short task.",
        "4. Do not run long loops inside OpenCode bash.",
    ])
    atomic_write_text(STATE / "RESUME_PLAN.md", text)

def update_compact_handoff(note: str = "") -> None:
    active = get_active_task()
    checkpoint = read_json(STATE / "CHECKPOINT.json", {})
    run_state = read_json(STATE / "RUN_STATE.json", {})
    text = "\n".join([
        "# Compact Handoff",
        "",
        "This file is a durable handoff after OpenCode compaction.",
        "",
        f"- Updated: {now()}",
        f"- Stop requested: `{is_stop_requested()}`",
        "",
        "## Safety rule",
        "Anything listed here is planned, not approved. Do not perform risk:review_required actions without explicit current-session user approval.",
        "",
        "## Run state",
        "```json",
        json.dumps(run_state, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Active task",
        "```json",
        json.dumps(active, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Checkpoint",
        "```json",
        json.dumps(checkpoint, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Latest note",
        note or "No note.",
    ])
    atomic_write_text(STATE / "COMPACT_HANDOFF.md", text)

def append_blocker(message: str) -> None:
    text = read_text(STATE / "BLOCKERS.md")
    atomic_write_text(STATE / "BLOCKERS.md", text.rstrip() + f"\n\n## {now()}\n\n{message}\n")
    append_jsonl(LOGS / "blockers.jsonl", {"timestamp": now(), "message": message})

def append_done(message: str) -> None:
    text = read_text(STATE / "DONE_LOG.md")
    atomic_write_text(STATE / "DONE_LOG.md", text.rstrip() + f"\n\n## {now()}\n\n{message}\n")
    append_jsonl(LOGS / "done_log.jsonl", {"timestamp": now(), "message": message})
