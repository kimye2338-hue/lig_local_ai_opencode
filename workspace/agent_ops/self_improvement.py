# -*- coding: utf-8 -*-
"""Automatic self-improvement loop for OpenCodeLIG.

This is intentionally small and append-only. It records compact observations
about model/tool mistakes, links a later success in the same task/run to a fix,
and exposes a tiny set of actionable lessons for the next session.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_SETTINGS = {
    "enabled": True,
    "auto_capture": True,
    "auto_promote": True,
    "auto_inject": True,
    "auto_wiki": True,
    "max_injected": 3,
}

EVENTS = "events.jsonl"
LESSONS = "lessons.jsonl"
SETTINGS = "settings.json"
REPORT = "report.md"

_SECRET_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._\-+/=]+", re.I),
    re.compile(r"(api[_-]?key\s*[=:]\s*)[^\s,;]+", re.I),
    re.compile(r"(password\s*[=:]\s*)[^\s,;]+", re.I),
]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def base_dir() -> Path:
    explicit = os.environ.get("LIG_SELF_IMPROVEMENT_DIR")
    if explicit:
        return Path(explicit)
    return Path.home() / "OpenCodeLIG_USERDATA" / "self_improvement"


def _userdata_dir() -> Path:
    explicit = os.environ.get("OPENCODE_USERDATA")
    if explicit:
        return Path(explicit)
    return Path.home() / "OpenCodeLIG_USERDATA"


def _path(name: str) -> Path:
    return base_dir() / name


def _ensure() -> None:
    base_dir().mkdir(parents=True, exist_ok=True)
    if not _path(SETTINGS).exists():
        _write_json(_path(SETTINGS), DEFAULT_SETTINGS)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except Exception:
        return default


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
    except Exception:
        pass
    return rows


def _append_jsonl(path: Path, item: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(item, ensure_ascii=False) + "\n")


def _redact(text: Any, limit: int = 500) -> str:
    value = str(text or "").replace("\r", " ").replace("\n", " ")
    value = " ".join(value.split())
    for pat in _SECRET_PATTERNS:
        value = pat.sub(lambda m: (m.group(1) if m.groups() else "Bearer ") + "<hidden>", value)
    return value[:limit]


def _signature(*parts: str) -> str:
    import hashlib
    raw = "|".join(_redact(p, 300).lower() for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def get_settings() -> Dict[str, Any]:
    _ensure()
    settings = dict(DEFAULT_SETTINGS)
    stored = _read_json(_path(SETTINGS), {})
    if isinstance(stored, dict):
        settings.update(stored)
    return settings


def save_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(DEFAULT_SETTINGS)
    merged.update(settings or {})
    _write_json(_path(SETTINGS), merged)
    return merged


def set_enabled(enabled: bool) -> Dict[str, Any]:
    settings = get_settings()
    settings["enabled"] = bool(enabled)
    return save_settings(settings)


def enabled() -> bool:
    s = get_settings()
    return bool(s.get("enabled", True) and s.get("auto_capture", True))


def record_event(kind: str, area: str, *, failure: str = "", fix: str = "",
                 next_action: str = "", task: str = "", run_id: str = "",
                 route: str = "", source: str = "auto",
                 metadata: Optional[Dict[str, Any]] = None,
                 force: bool = False) -> Optional[Dict[str, Any]]:
    """Append one compact self-improvement event. Returns None when disabled."""
    if not force and not enabled():
        return None
    _ensure()
    item = {
        "id": "si_" + uuid.uuid4().hex[:10],
        "created_at": now_iso(),
        "kind": kind,
        "status": "active",
        "area": _redact(area, 80),
        "failure": _redact(failure, 500),
        "fix": _redact(fix, 500),
        "next_action": _redact(next_action, 300),
        "task": _redact(task, 160),
        "run_id": _redact(run_id, 80),
        "route": _redact(route, 80),
        "source": source,
        "signature": _signature(kind, area, failure, next_action or fix),
        "metadata": metadata or {},
    }
    _append_jsonl(_path(EVENTS), item)
    if kind in {"self_fix", "self_lesson"}:
        _upsert_lesson(item)
    if get_settings().get("auto_wiki", True):
        render_report()
    return item


def record_error(area: str, detail: str, *, task: str = "", run_id: str = "",
                 route: str = "", source: str = "auto") -> Optional[Dict[str, Any]]:
    return record_event(
        "self_error",
        area,
        failure=detail,
        task=task,
        run_id=run_id,
        route=route,
        source=source,
    )


def record_fix(area: str, failure: str, fix: str, next_action: str, *,
               task: str = "", run_id: str = "", route: str = "",
               source: str = "auto") -> Optional[Dict[str, Any]]:
    return record_event(
        "self_fix",
        area,
        failure=failure,
        fix=fix,
        next_action=next_action,
        task=task,
        run_id=run_id,
        route=route,
        source=source,
    )


def _matching_unresolved_error(task: str, run_id: str, area: str) -> Optional[Dict[str, Any]]:
    events = list(reversed(_read_jsonl(_path(EVENTS))))
    task_norm = _redact(task, 160)
    run_norm = _redact(run_id, 80)
    area_norm = _redact(area, 80)
    for item in events[:40]:
        if item.get("kind") != "self_error":
            continue
        if run_norm and item.get("run_id") == run_norm:
            return item
        if task_norm and item.get("task") == task_norm:
            return item
        if area_norm and item.get("area") == area_norm:
            return item
    return None


def capture_task_result(task: str, *, ok: bool, area: str = "task",
                        detail: str = "", run_id: str = "", route: str = "") -> Optional[Dict[str, Any]]:
    """Record failure, or link a later success to the most recent failure."""
    if ok:
        prev = _matching_unresolved_error(task, run_id, area)
        if not prev:
            return None
        fix = detail or route or "later successful path"
        next_action = (
            f"다음에는 `{prev.get('area')}` 작업에서 같은 증상('{prev.get('failure')}')이 보이면 "
            f"방금 성공한 방법({fix})을 먼저 적용한다."
        )
        return record_fix(
            str(prev.get("area") or area),
            str(prev.get("failure") or detail),
            fix,
            next_action,
            task=task,
            run_id=run_id,
            route=route,
        )
    return record_error(area, detail, task=task, run_id=run_id, route=route)


def _upsert_lesson(event: Dict[str, Any]) -> Dict[str, Any]:
    lessons = _read_jsonl(_path(LESSONS))
    sig = _signature(str(event.get("area")), str(event.get("failure")), str(event.get("next_action")))
    for row in lessons:
        if row.get("signature") == sig:
            row["count"] = int(row.get("count") or 1) + 1
            row["updated_at"] = now_iso()
            row["priority"] = "high" if row["count"] >= 2 else row.get("priority", "normal")
            row["fix"] = event.get("fix", row.get("fix", ""))
            _rewrite_jsonl(_path(LESSONS), lessons)
            return row
    lesson = {
        "id": "sil_" + uuid.uuid4().hex[:10],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "kind": "self_lesson",
        "status": "active",
        "priority": "normal",
        "area": event.get("area", ""),
        "failure": event.get("failure", ""),
        "fix": event.get("fix", ""),
        "next_action": event.get("next_action", "") or event.get("fix", ""),
        "count": 1,
        "signature": sig,
    }
    lessons.append(lesson)
    _rewrite_jsonl(_path(LESSONS), lessons)
    return lesson


def _rewrite_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    tmp.replace(path)


def lessons_for_injection(limit: int | None = None) -> List[Dict[str, Any]]:
    settings = get_settings()
    if not settings.get("enabled", True) or not settings.get("auto_inject", True):
        return []
    max_items = int(limit if limit is not None else settings.get("max_injected", 3))
    rows = [r for r in _read_jsonl(_path(LESSONS)) if r.get("status") == "active"]
    indexed = list(enumerate(rows))
    indexed.sort(key=lambda pair: pair[0], reverse=True)
    indexed.sort(key=lambda pair: str(pair[1].get("updated_at") or pair[1].get("created_at", "")), reverse=True)
    indexed.sort(key=lambda pair: int(pair[1].get("count") or 1), reverse=True)
    indexed.sort(key=lambda pair: 0 if pair[1].get("priority") == "high" else 1)
    return [row for _idx, row in indexed[:max(0, max_items)]]


def format_injection_block(limit: int | None = None) -> str:
    lessons = lessons_for_injection(limit=limit)
    if not lessons:
        return ""
    lines = ["## OpenCodeLIG 자가개선 지침", "같은 시행착오를 반복하지 않도록 우선 적용:"]
    for row in lessons:
        action = _redact(row.get("next_action") or row.get("fix"), 220)
        if action:
            lines.append(f"- {action}")
    return "\n".join(lines)


def render_report() -> Path:
    _ensure()
    events = _read_jsonl(_path(EVENTS))
    lessons = _read_jsonl(_path(LESSONS))
    lines = [
        "# Self Improvement Report",
        "",
        f"- updated: `{now_iso()}`",
        f"- enabled: `{get_settings().get('enabled', True)}`",
        f"- events: `{len(events)}`",
        f"- lessons: `{len(lessons)}`",
        "",
        "## Active Lessons",
    ]
    active = [r for r in lessons if r.get("status") == "active"]
    if not active:
        lines.append("- 없음")
    for row in active[-20:]:
        lines.append(f"- **{row.get('area')}**: {row.get('next_action')} (count={row.get('count')})")
    path = _path(REPORT)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if get_settings().get("auto_wiki", True):
        _render_wiki_summary(lines)
    return path


def _render_wiki_summary(lines: List[str]) -> None:
    try:
        wiki_dir = _userdata_dir() / "memory" / "wiki" / "self-improvement"
        wiki_dir.mkdir(parents=True, exist_ok=True)
        (wiki_dir / "0-자가개선-대시보드.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def status() -> Dict[str, Any]:
    _ensure()
    return {
        "settings": get_settings(),
        "dir": str(base_dir()),
        "events": len(_read_jsonl(_path(EVENTS))),
        "lessons": len(_read_jsonl(_path(LESSONS))),
    }
