# -*- coding: utf-8 -*-
from __future__ import annotations

import concurrent.futures as cf
import json
import time
from typing import Any, Dict

from .core import RESULTS, LOGS, now, atomic_write_text, append_jsonl, is_stop_requested
from .queue_manager import get_next_task, get_next_batch, mark_task_running, mark_task_done, mark_task_failed, summary
from .state_manager import heartbeat, set_active_task, update_checkpoint, append_done, append_blocker
from .failures import log_failure, make_selfheal_plan
from .doctor import run_doctor
from .verifier import verify
from .reporter import write_report
from .memory_manager import memorycheck, recall, extract_keywords, format_recall_for_prompt, record_success_lesson
from .safety import classify_action, scan_jsonl_file
from .llm_client import chat, is_configured

def execute_task(task: Dict[str, Any]) -> Dict[str, Any]:
    kind = task.get("kind", "manual")
    payload = task.get("payload", {}) or {}
    if kind == "doctor":
        return {"ok": True, "result": run_doctor()}
    if kind == "verify":
        result = verify()
        return {"ok": bool(result.get("ok")), "result": result}
    if kind == "report":
        return {"ok": True, "result": write_report()}
    if kind == "memorycheck":
        return {"ok": True, "result": memorycheck()}
    if kind == "selfheal":
        return {"ok": True, "result": make_selfheal_plan()}
    if kind == "safety_check":
        return {"ok": True, "result": classify_action(payload.get("data", ""))}
    if kind == "safety_scan":
        return {"ok": True, "result": scan_jsonl_file(payload.get("source", "clickable_elements.jsonl"))}
    if kind == "llm_plan":
        if not is_configured():
            return {"ok": False, "error": "LLM not configured; set AGENTOPS_LLM_BASE_URL/API_KEY/MODEL"}
        prompt = payload.get("prompt") or task.get("title") or "Continue current task."
        keywords = extract_keywords(" ".join([task.get("title", ""), task.get("kind", ""), json.dumps(payload, ensure_ascii=False)]))
        memories = recall(task_kind=kind, keywords=keywords, limit=6)
        memory_block = format_recall_for_prompt(memories)
        system = "\n".join([
            "You are an AgentOps specialist. Produce a concise, actionable result.",
            "Do not claim you executed tools unless this task explicitly includes execution output.",
            "",
            "RELEVANT PRIOR MEMORY / USER PREFERENCES / FAILURE LESSONS:",
            memory_block,
            "",
            "Use the recalled lessons to avoid repeating prior failures.",
        ])
        content = chat([{"role": "system", "content": system}, {"role": "user", "content": prompt}])
        out = RESULTS / "llm_responses" / (task["task_id"] + ".md")
        atomic_write_text(out, content)
        return {"ok": True, "result": {"output_file": str(out), "memory_items_used": [m.get("id") for m in memories]}}
    if kind == "reflect":
        report = memorycheck()
        return {"ok": True, "result": report}
    if kind == "manual":
        append_blocker(f"Manual task requires OpenCode/supervisor handling: {task.get('task_id')} {task.get('title')}")
        return {"ok": False, "error": "manual task requires supervisor"}
    return {"ok": False, "error": f"unknown task kind: {kind}"}

def run_task(task: Dict[str, Any]) -> Dict[str, Any]:
    task = mark_task_running(task)
    set_active_task(task)
    update_checkpoint(f"running task {task.get('task_id')}")
    try:
        result = execute_task(task)
        if result.get("ok"):
            mark_task_done(task, result)
            append_done(f"Task done: {task.get('task_id')} {task.get('title')}")
            try:
                record_success_lesson(task, result.get("result", {}))
            except Exception as exc:
                append_jsonl(LOGS / "memory_errors.jsonl", {"timestamp": now(), "error": repr(exc)})
            update_checkpoint(f"task done {task.get('task_id')}")
            return {"ok": True, "status": "done", "task": task, "result": result}
        failure = log_failure(str(result.get("error", result)), source="orchestrator", task_id=task.get("task_id", ""))
        mark_task_failed(task, str(result.get("error", result)), failure.get("type", "UNKNOWN"))
        update_checkpoint(f"task failed {task.get('task_id')}")
        return {"ok": False, "status": "failed", "task": task, "failure": failure}
    except Exception as exc:
        failure = log_failure(repr(exc), source="orchestrator_exception", task_id=task.get("task_id", ""))
        mark_task_failed(task, repr(exc), failure.get("type", "UNKNOWN"))
        update_checkpoint(f"task exception {task.get('task_id')}")
        return {"ok": False, "status": "exception", "task": task, "failure": failure}

def run_once() -> Dict[str, Any]:
    heartbeat("orchestrator_once")
    if is_stop_requested():
        return {"ok": True, "status": "stopped"}
    task = get_next_task()
    if not task:
        update_checkpoint("orchestrator idle")
        return {"ok": True, "status": "idle", "queue": summary()}
    return run_task(task)

def run_loop(interval_seconds: int = 60) -> int:
    heartbeat("continuous_external")
    while not is_stop_requested():
        result = run_once()
        append_jsonl(LOGS / "orchestrator_loop.jsonl", {"timestamp": now(), "result": result})
        time.sleep(max(10, interval_seconds))
    heartbeat("stopped")
    update_checkpoint("orchestrator stopped by STOP")
    return 0

def run_loop_parallel(interval_seconds: int = 60, max_workers: int = 3) -> int:
    heartbeat("continuous_parallel")
    while not is_stop_requested():
        batch = get_next_batch(max_workers=max_workers)
        if not batch:
            update_checkpoint("orchestrator parallel idle")
            time.sleep(max(10, interval_seconds))
            continue
        with cf.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(run_task, task): task for task in batch}
            for fut in cf.as_completed(futures):
                task = futures[fut]
                try:
                    result = fut.result()
                except Exception as exc:
                    result = {"ok": False, "status": "parallel_exception", "task": task, "error": repr(exc)}
                append_jsonl(LOGS / "orchestrator_parallel.jsonl", {"timestamp": now(), "result": result})
        time.sleep(max(5, interval_seconds))
    heartbeat("stopped")
    update_checkpoint("orchestrator parallel stopped by STOP")
    return 0
