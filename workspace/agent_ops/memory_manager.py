# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional

from .core import MEMORY, REPORTS, now, read_jsonl, write_jsonl, atomic_write_text, read_text, file_lock

MEMORY_JSONL = MEMORY / "memory.jsonl"
MAX_RENDER = 40

def ensure_memory() -> None:
    MEMORY.mkdir(parents=True, exist_ok=True)
    if not MEMORY_JSONL.exists():
        write_jsonl(MEMORY_JSONL, [])
        # 뷰 렌더는 원장을 처음 만들 때 1회만. 매 읽기(recall/load_memory)마다
        # 렌더하면 조회 한 번에 USERDATA 파일 5~6개를 다시 쓰는 churn이 생긴다.
        # 이후 갱신은 쓰기 경로(add_memory_event/memorycheck)가 담당한다.
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
        # Hard cap on active memory: 초과 시 **가치 낮은 것부터** 아카이브한다.
        # 사용자 규칙/선호(source=user)·high 우선순위는 활동 기록이 아무리 쌓여도
        # 밀려나지 않게 보호한다 (활동 자동적재로 규칙이 사라지면 안 되므로).
        MAX_ACTIVE = 500
        active_rows = [r for r in rows if r.get("status") == "active"]
        if len(active_rows) > MAX_ACTIVE:
            overflow = sorted(active_rows,
                              key=lambda r: (_protect_rank(r), str(r.get("created_at", "")))
                              )[:len(active_rows) - MAX_ACTIVE]
            ids = {r.get("id") for r in overflow if r.get("id")}
            for r in rows:
                if r.get("id") in ids:
                    r["status"] = "deprecated"
                    r["deprecated_reason"] = "memory cap exceeded; auto-archived (lowest value first)"
        write_jsonl(MEMORY_JSONL, rows)
    render_memory_views()
    # ingest 워크플로(LLM Wiki): 새 기록이 들어올 때마다 주제 페이지를 갱신한다.
    # 기록이 쌓일수록 같은 페이지가 두꺼워지는 복리 구조 — 실패해도 저장은 유효.
    try:
        from .wiki_manager import consolidate_quietly
        consolidate_quietly()
    except Exception:
        pass
    return item

def _protect_rank(row: Dict[str, Any]) -> int:
    """캡 초과 시 아카이브 우선순위(작을수록 먼저 아카이브 = 보호 약함).

    사용자 규칙/선호와 high 우선순위는 크게 가산해 활동 기록 홍수에도 살아남게 한다.
    """
    kind_rank = {"activity": 0, "log": 1, "note": 1, "lesson": 2,
                 "error_pattern": 2, "preference": 3}.get(str(row.get("kind")), 1)
    if row.get("source") == "user":
        kind_rank += 10
    if row.get("priority") == "high":
        kind_rank += 5
    return kind_rank


def add_activity(task: str, outcome: str = "", tags: List[str] | None = None) -> Optional[Dict[str, Any]]:
    """완료된 작업을 **간결하게** 기억에 자동 적재 → 증류되어 위키(Obsidian)에 정리된다.

    - kind='activity', priority='low' (규칙/교훈보다 낮음, 캡에서 먼저 밀림).
    - 같은 날 같은 제목은 한 번만(중복 홍수 방지). 빈 작업은 무시.
    - recall 은 activity 에 가점을 안 주므로 사용자 규칙 회상을 밀어내지 않는다.
    """
    task = (task or "").strip()
    if not task:
        return None
    title = task[:70]
    today = now()[:10]
    for r in load_memory(status="active"):
        if r.get("kind") == "activity" and r.get("title") == title \
                and str(r.get("created_at", ""))[:10] == today:
            return None  # 오늘 같은 작업 이미 기록됨
    body = (outcome or "").strip()[:280]
    return add_memory_event("activity", title, body, status="active",
                            priority="low", source="agent",
                            tags=(tags or extract_keywords(task + " " + body)[:6]))


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
        text += " " + " ".join(str(t) for t in (row.get("tags") or [])).lower()
        score = 0
        if task_kind and task_kind.lower() in text:
            score += 2
        score += sum(1 for k in keys if k and k in text)
        # 질의와 최소 1개 이상 일치한 행에만 kind/source/priority 보너스를 얹는다.
        # 무조건 가점이면 사용자 규칙(user/high, 기본 6점)이 어떤 질의에서도
        # limit(6)를 점유해 진짜 관련 기억을 밀어낸다 — 상시 노출은 pinned_recall 담당.
        if score <= 0:
            continue
        if row.get("kind") in {"lesson", "error_pattern", "preference"}:
            score += 1
        if row.get("source") == "user":
            score += 3
        if row.get("priority") == "high":
            score += 2
        scored.append((score, row))
    scored.sort(key=lambda x: (-x[0], str(x[1].get("created_at", ""))))
    return [r for _, r in scored[:limit]]

def pinned_recall(limit: int = 5, error_days: int = 14) -> List[Dict[str, Any]]:
    """키워드와 무관하게 '항상' 주입할 기억 — 회상 보장의 핵심.

    recall 은 키워드 점수제라 작업 문구가 다르면 놓칠 수 있다. 하지만
    ① 사용자가 직접 시킨 규칙(source=user)과 ② 최근 자가 관찰 실수
    (error_pattern)는 어떤 작업에서든 반영돼야 한다 — "기억해놓으면 꼭 회상".
    """
    ensure_memory()
    rows = load_memory(status="active")
    user_prefs = [r for r in rows if r.get("source") == "user"]
    # 우선순위 high 먼저, 같은 급에서는 최신 먼저 (안정 정렬 2단).
    user_prefs.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
    user_prefs.sort(key=lambda r: 0 if r.get("priority") == "high" else 1)
    cutoff = now()[:10]
    try:
        from datetime import datetime, timedelta
        cutoff = (datetime.fromisoformat(now()[:10]) - timedelta(days=error_days)).strftime("%Y-%m-%d")
    except Exception:
        pass
    recent_errors = sorted(
        [r for r in rows if r.get("kind") == "error_pattern"
         and str(r.get("created_at", ""))[:10] >= cutoff],
        key=lambda r: str(r.get("created_at", "")), reverse=True)
    picked: List[Dict[str, Any]] = []
    seen: set = set()
    for r in user_prefs[:limit] + recent_errors[:max(2, limit - 2)]:
        if r.get("id") not in seen:
            seen.add(r.get("id"))
            picked.append(r)
    return picked[: limit + 2]


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

def record_self_error(area: str, detail: str, task: str = "") -> None:
    """시스템이 '스스로 관찰한' 실수를 기억에 남긴다 — 사람이 안 불러줘도.

    호출처: 품질검증이 LLM 출력을 거부했을 때, 어댑터 실행이 실패했을 때.
    같은 제목이 같은 날 이미 있으면 중복 기록하지 않는다(원장 오염 방지).
    기록된 error_pattern은 recall 기계주입으로 다음 작업에 자동 반영된다.
    """
    title = f"자가 관찰 실수: {area}"
    today = now()[:10]
    for r in load_memory():
        if r.get("title") == title and str(r.get("created_at", ""))[:10] == today:
            return
    body = (detail or "")[:300] + (f" (작업: {task[:80]})" if task else "")
    add_memory_event("error_pattern", title, body, status="active",
                     priority="normal", source="self_observed",
                     tags=extract_keywords(area + " " + task)[:6])


def record_success_lesson(task: Dict[str, Any], result: Dict[str, Any]) -> None:
    kind = task.get("kind", "task")
    if kind in {"memorycheck", "report", "verify", "doctor", "reflect"}:
        return  # routine maintenance success is not a lesson
    title = f"Successful task pattern: {kind}"
    today = now()[:10]
    for r in load_memory(status="active"):
        if r.get("title") == title and str(r.get("created_at", ""))[:10] == today:
            return  # already captured today
    body = f"Task `{task.get('task_id')}` ({kind}) succeeded: {task.get('title')}."
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
    # 위키 정리 루틴: 페이지 재통합 + lint(중복/고아/정체 보고 — 자동 삭제 없음).
    wiki_report: Dict[str, Any] = {}
    try:
        from .wiki_manager import consolidate, lint
        wiki_report = {"consolidate": consolidate(), "lint": lint()}
    except Exception as exc:
        wiki_report = {"error": exc.__class__.__name__}
    report = {
        "timestamp": now(),
        "index": json.loads(read_text(MEMORY / "MEMORY_INDEX.json") or "{}"),
        "update_plan": plan,
        "wiki": wiki_report,
    }
    atomic_write_text(REPORTS / "MEMORY_REVIEW.md", "# Memory Review\n\n```json\n" + json.dumps(report, ensure_ascii=False, indent=2) + "\n```\n")
    return report
