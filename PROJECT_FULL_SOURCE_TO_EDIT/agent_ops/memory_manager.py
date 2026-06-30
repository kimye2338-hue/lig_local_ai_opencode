# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List

from .core import MEMORY, REPORTS, now, read_jsonl, write_jsonl, atomic_write_text, read_text, file_lock

MEMORY_JSONL = MEMORY / "memory.jsonl"
MAX_RENDER = 40

def ensure_memory() -> None:
    MEMORY.mkdir(parents=True, exist_ok=True)
    if not MEMORY_JSONL.exists():
        write_jsonl(MEMORY_JSONL, [])
    render_memory_views()

def add_memory_event(kind: str, title: str, body: str, status: str = "active", priority: str = "normal", source: str = "manual", supersedes: List[str] | None = None, tags: List[str] | None = None) -> Dict[str, Any]:
    ensure_memory()
    with file_lock("memory"):
        rows = [r for r in read_jsonl(MEMORY_JSONL) if isinstance(r, dict)]
        item = {
            "id": "mem_" + uuid.uuid4().hex[:10],
            "created_at": now(),
            "updated_at": now(),
            "kind": kind,
            "status": status,
            "priority": priority,
            "source": source,
            "title": title,
            "body": body,
            "tags": tags or [],
            "supersedes": supersedes or [],
            "superseded_by": None,
            "review_after_days": 14,
        }
        rows.append(item)
        write_jsonl(MEMORY_JSONL, rows)
    render_memory_views()
    return item

def add_user_memory(text: str, title: str = "User instruction") -> Dict[str, Any]:
    return add_memory_event(
        kind="preference",
        title=title,
        body=text,
        status="active",
        priority="high",
        source="user",
        tags=extract_keywords(text)[:8],
    )

def load_memory(status: str | None = None) -> List[Dict[str, Any]]:
    ensure_memory()
    rows = [r for r in read_jsonl(MEMORY_JSONL) if isinstance(r, dict)]
    if status:
        rows = [r for r in rows if r.get("status") == status]
    return rows

def extract_keywords(text: str, limit: int = 20) -> List[str]:
    raw = re.findall(r"[A-Za-z0-9_./:-]{3,}|[가-힣]{2,}", text or "")
    stop = {"the", "and", "for", "with", "this", "that", "from", "json", "file", "task", "해야", "있는", "없는", "그리고"}
    out: List[str] = []
    for w in raw:
        lw = w.lower()
        if lw in stop:
            continue
        if lw not in out:
            out.append(lw)
        if len(out) >= limit:
            break
    return out

def recall(task_kind: str = "", keywords: List[str] | None = None, limit: int = 6) -> List[Dict[str, Any]]:
    ensure_memory()
    keys = [k.lower() for k in (keywords or []) if k]
    rows = load_memory(status="active")
    scored: List[tuple[int, Dict[str, Any]]] = []
    for row in rows:
        text = " ".join(str(row.get(k, "")) for k in ["title", "body", "kind", "priority", "source"]).lower()
        score = 0
        if task_kind and task_kind.lower() in text:
            score += 2
        score += sum(1 for k in keys if k and k in text)
        if row.get("kind") in {"lesson", "error_pattern", "preference"}:
            score += 1
        if row.get("source") == "user":
            score += 3
        if row.get("priority") == "high":
            score += 2
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda x: (-x[0], str(x[1].get("created_at", ""))))
    return [r for _, r in scored[:limit]]

def format_recall_for_prompt(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "No relevant prior memory found."
    lines = []
    for item in items:
        body = str(item.get("body", "")).strip().replace("\n", " ")
        if len(body) > 500:
            body = body[:500] + "..."
        lines.append(f"- [{item.get('kind')}/{item.get('priority')}/{item.get('source')}] {item.get('title')}: {body}")
    return "\n".join(lines)

def record_success_lesson(task: Dict[str, Any], result: Dict[str, Any]) -> None:
    title = f"Successful task pattern: {task.get('kind', 'task')}"
    body = f"Task `{task.get('task_id')}` succeeded. Title: {task.get('title')}. Owner: {task.get('owner_agent')}. Result keys: {', '.join(result.keys()) if isinstance(result, dict) else 'n/a'}."
    add_memory_event("lesson", title, body, status="active", priority="normal", source="task_success", tags=extract_keywords(task.get("title", "")))

def propose_memory_update(reason: str = "") -> Dict[str, Any]:
    rows = load_memory()
    active = [r for r in rows if r.get("status") == "active"]
    proposals: List[Dict[str, Any]] = []
    seen_titles: Dict[str, str] = {}
    for r in active:
        title = str(r.get("title", "")).strip().lower()
        if title in seen_titles:
            proposals.append({"action": "mark_needs_review", "target_id": r.get("id"), "reason": f"duplicate-like title with {seen_titles[title]}"})
        elif title:
            seen_titles[title] = r.get("id", "")
    plan = {"timestamp": now(), "reason": reason, "proposals": proposals}
    atomic_write_text(MEMORY / "MEMORY_UPDATE_PLAN.md", "# Memory Update Plan\n\n```json\n" + json.dumps(plan, ensure_ascii=False, indent=2) + "\n```\n")
    return plan

def render_memory_views() -> None:
    MEMORY.mkdir(parents=True, exist_ok=True)
    rows = [r for r in read_jsonl(MEMORY_JSONL) if isinstance(r, dict)]
    by_status: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_status.setdefault(str(r.get("status", "unknown")), []).append(r)
    mapping = {"active": "ACTIVE_MEMORY.md", "resolved": "RESOLVED_MEMORY.md", "deprecated": "DEPRECATED_MEMORY.md"}
    for status, filename in mapping.items():
        items = by_status.get(status, [])[-MAX_RENDER:]
        lines = [f"# {status.title()} Memory", "", f"Rendered from `memory.jsonl` at {now()}.", ""]
        if not items:
            lines.append("No entries.")
        for item in items:
            lines += [
                f"## {item.get('title','(untitled)')}",
                "",
                f"- id: `{item.get('id')}`",
                f"- kind: `{item.get('kind')}`",
                f"- priority: `{item.get('priority')}`",
                f"- source: `{item.get('source')}`",
                "",
                str(item.get("body", "")).strip(),
                "",
            ]
        atomic_write_text(MEMORY / filename, "\n".join(lines))
    lessons = [r for r in rows if r.get("kind") in {"lesson", "error_pattern", "preference"}][-MAX_RENDER:]
    lesson_lines = ["# Lessons Learned, Preferences, and Error Patterns", "", f"Rendered at {now()}.", ""]
    for item in lessons:
        lesson_lines += [f"## {item.get('title')}", "", str(item.get("body","")).strip(), ""]
    atomic_write_text(MEMORY / "LESSONS_LEARNED.md", "\n".join(lesson_lines))
    atomic_write_text(MEMORY / "MEMORY_INDEX.json", json.dumps({
        "updated_at": now(),
        "total": len(rows),
        "counts": {status: len(items) for status, items in by_status.items()},
        "source_of_truth": ".agent-memory/memory.jsonl",
    }, ensure_ascii=False, indent=2))

def memorycheck() -> Dict[str, Any]:
    ensure_memory()
    plan = propose_memory_update("routine memorycheck")
    render_memory_views()
    report = {
        "timestamp": now(),
        "index": json.loads(read_text(MEMORY / "MEMORY_INDEX.json") or "{}"),
        "update_plan": plan,
    }
    atomic_write_text(REPORTS / "MEMORY_REVIEW.md", "# Memory Review\n\n```json\n" + json.dumps(report, ensure_ascii=False, indent=2) + "\n```\n")
    return report
