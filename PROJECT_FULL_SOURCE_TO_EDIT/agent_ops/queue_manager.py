# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Set

from .core import STATE, now, read_jsonl, write_jsonl, file_lock
from .state_manager import append_blocker

QUEUE = STATE / "TASK_QUEUE.jsonl"
DEFAULT_MAX_RETRIES = 3

def normalize_task(task: Dict[str, Any]) -> Dict[str, Any]:
    t = dict(task or {})
    t.setdefault("task_id", "task_" + uuid.uuid4().hex[:10])
    t.setdefault("priority", 5)
    t.setdefault("status", "pending")
    t.setdefault("title", "")
    t.setdefault("kind", "manual")
    t.setdefault("owner_agent", "agentops-supervisor")
    t.setdefault("depends_on", [])
    t.setdefault("touches", [])
    t.setdefault("attempt_count", 0)
    t.setdefault("max_retries", DEFAULT_MAX_RETRIES)
    t.setdefault("blocked_reason", None)
    t.setdefault("risk", "safe")
    t.setdefault("payload", {})
    t.setdefault("created_at", now())
    t["updated_at"] = now()
    return t

def load_tasks() -> List[Dict[str, Any]]:
    rows = read_jsonl(QUEUE)
    tasks: List[Dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict) and not row.get("parse_error"):
            tasks.append(normalize_task(row))
    return tasks

def save_tasks(tasks: List[Dict[str, Any]]) -> None:
    write_jsonl(QUEUE, tasks)

def enqueue_task(title: str, kind: str = "manual", owner_agent: str = "agentops-supervisor", priority: int = 5, risk: str = "safe", payload: Optional[Dict[str, Any]] = None, depends_on: Optional[List[str]] = None, touches: Optional[List[str]] = None) -> Dict[str, Any]:
    with file_lock("task_queue"):
        tasks = load_tasks()
        task = normalize_task({
            "title": title,
            "kind": kind,
            "owner_agent": owner_agent,
            "priority": priority,
            "risk": risk,
            "payload": payload or {},
            "depends_on": depends_on or [],
            "touches": touches or [],
        })
        tasks.append(task)
        save_tasks(tasks)
    return task

def task_by_id(tasks: List[Dict[str, Any]], task_id: str) -> Optional[Dict[str, Any]]:
    for task in tasks:
        if task.get("task_id") == task_id:
            return task
    return None

def dependencies_done(task: Dict[str, Any], tasks: List[Dict[str, Any]]) -> bool:
    for dep in task.get("depends_on") or []:
        other = task_by_id(tasks, dep)
        if not other or other.get("status") != "done":
            return False
    return True

def get_next_task() -> Optional[Dict[str, Any]]:
    tasks = load_tasks()
    candidates = [t for t in tasks if t.get("status") == "pending" and dependencies_done(t, tasks)]
    if not candidates:
        return None
    candidates.sort(key=lambda t: (int(t.get("priority", 5)), str(t.get("created_at", ""))))
    return candidates[0]

def _touches_conflict(a: Dict[str, Any], touched: Set[str]) -> bool:
    touches = set(str(x) for x in (a.get("touches") or []))
    if not touches:
        return False
    return bool(touches & touched)

def _is_parallel_safe(task: Dict[str, Any]) -> bool:
    # File-writing/repair tasks must remain serial.
    if task.get("kind") in {"safe_write", "repair", "memory_apply"}:
        return False
    if task.get("owner_agent") in {"agentops-repair"}:
        return False
    return task.get("risk") != "review_required"

def get_next_batch(max_workers: int = 3) -> List[Dict[str, Any]]:
    tasks = load_tasks()
    candidates = [t for t in tasks if t.get("status") == "pending" and dependencies_done(t, tasks)]
    candidates.sort(key=lambda t: (int(t.get("priority", 5)), str(t.get("created_at", ""))))
    batch: List[Dict[str, Any]] = []
    touched: Set[str] = set()
    for task in candidates:
        if len(batch) >= max_workers:
            break
        if batch and not _is_parallel_safe(task):
            continue
        if _touches_conflict(task, touched):
            continue
        batch.append(task)
        touched.update(str(x) for x in (task.get("touches") or []))
    return batch

def update_task(task_id: str, **updates: Any) -> Optional[Dict[str, Any]]:
    with file_lock("task_queue"):
        tasks = load_tasks()
        found = None
        for idx, task in enumerate(tasks):
            if task.get("task_id") == task_id:
                task.update(updates)
                task["updated_at"] = now()
                tasks[idx] = normalize_task(task)
                found = tasks[idx]
                break
        save_tasks(tasks)
    return found

def mark_task_running(task: Dict[str, Any]) -> Dict[str, Any]:
    attempts = int(task.get("attempt_count") or 0) + 1
    return update_task(task["task_id"], status="active", attempt_count=attempts) or task

def mark_task_done(task: Dict[str, Any], result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return update_task(task["task_id"], status="done", result=result or {}, blocked_reason=None) or task

def mark_task_failed(task: Dict[str, Any], reason: str, failure_type: str = "UNKNOWN") -> Dict[str, Any]:
    attempts = int(task.get("attempt_count") or 0)
    status = "failed" if attempts >= int(task.get("max_retries") or DEFAULT_MAX_RETRIES) else "pending"
    if status == "failed":
        append_blocker(f"Task failed permanently: {task.get('task_id')} {task.get('title')} / {failure_type}: {reason}")
    return update_task(task["task_id"], status=status, last_failure_type=failure_type, blocked_reason=reason) or task

def recover_interrupted_active_tasks(reason: str = "interrupted run") -> int:
    with file_lock("task_queue"):
        tasks = load_tasks()
        count = 0
        for task in tasks:
            if task.get("status") == "active":
                task["status"] = "pending"
                task["blocked_reason"] = reason
                task["updated_at"] = now()
                count += 1
        save_tasks(tasks)
    return count

def summary() -> Dict[str, Any]:
    tasks = load_tasks()
    counts: Dict[str, int] = {}
    for t in tasks:
        counts[t.get("status", "unknown")] = counts.get(t.get("status", "unknown"), 0) + 1
    return {"total": len(tasks), "counts": counts, "next_task": get_next_task()}
