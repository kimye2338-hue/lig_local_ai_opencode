# -*- coding: utf-8 -*-
"""Automatic self-improvement loop backed by the main memory ledger.

Settings/report stay in a small side directory, but failures/lessons use the
same memory.jsonl pipeline as the rest of OpenCodeLIG so recall/quality/decay
stay consistent and duplicate ledgers do not diverge.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
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

SETTINGS = "settings.json"
REPORT = "report.md"


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


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except Exception:
        return default


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
    settings = get_settings()
    return bool(settings.get("enabled", True) and settings.get("auto_capture", True))


def _memory_rows() -> List[Dict[str, Any]]:
    from .memory_manager import load_memory
    return [r for r in load_memory(status="active") if isinstance(r, dict)]


def _self_errors(area: str = "") -> List[Dict[str, Any]]:
    want = f"자가 관찰 실수: {area}" if area else ""
    rows = []
    for row in _memory_rows():
        if row.get("kind") != "error_pattern" or row.get("source") != "self_observed":
            continue
        if want and row.get("title") != want:
            continue
        rows.append(row)
    rows.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at", "")), reverse=True)
    return rows


def _self_fix_lessons() -> List[Dict[str, Any]]:
    rows = []
    for row in _memory_rows():
        if row.get("kind") == "lesson" and row.get("source") == "self_fix":
            rows.append(row)
    rows.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at", "")), reverse=True)
    return rows


def _dedupe_tag(row: Dict[str, Any]) -> str:
    for tag in row.get("tags") or []:
        tag = str(tag)
        if tag.startswith("dedupe:"):
            return tag
    return ""


def _task_marker(task: str) -> str:
    value = " ".join(str(task or "").split())[:80]
    return f"task:{value}" if value else ""


def record_error(area: str, detail: str, *, task: str = "", run_id: str = "",
                 route: str = "", source: str = "auto") -> Optional[Dict[str, Any]]:
    if not enabled():
        return None
    from .memory_manager import record_self_error
    return record_self_error(area, detail or "", task=task or "")


def _matching_error(task: str, area: str) -> Optional[Dict[str, Any]]:
    task_text = " ".join(str(task or "").split())[:80]
    for row in _self_errors(area):
        body = str(row.get("body", ""))
        if task_text and task_text in body:
            return row
    errors = _self_errors(area)
    return errors[0] if errors else None


def _existing_lesson(tag: str, action: str) -> Optional[Dict[str, Any]]:
    for row in _self_fix_lessons():
        if tag and tag not in [str(t) for t in (row.get("tags") or [])]:
            continue
        if str(row.get("body", "")) == action:
            return row
    return None


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def capture_task_result(task: str, *, ok: bool, area: str = "task",
                        detail: str = "", run_id: str = "", route: str = "") -> Optional[Dict[str, Any]]:
    if not enabled():
        return None
    if not ok:
        return record_error(area, detail, task=task, run_id=run_id, route=route, source="auto")

    error = _matching_error(task, area)
    if not error:
        return None

    dedupe = _dedupe_tag(error)
    fix = " ".join(str(detail or route or "성공한 경로를 우선 재사용").split())[:220]
    failure = " ".join(str(error.get("body", "")).split())[:220]
    action = f"{area}에서 '{failure}'가 다시 보이면 먼저 '{fix}' 순서로 처리한다."
    existing = _existing_lesson(dedupe, action)
    if existing and str(existing.get("created_at", ""))[:10] == _today():
        return existing

    from .memory_manager import add_memory_event, extract_keywords
    tags = [t for t in [dedupe, _task_marker(task), f"area:{area}"] if t]
    tags.extend(extract_keywords(f"{task} {area} {fix}")[:5])
    lesson = add_memory_event(
        "lesson",
        f"자가개선 교훈: {area}",
        action,
        status="active",
        priority="normal",
        source="self_fix",
        tags=tags,
    )
    if get_settings().get("auto_wiki", True):
        render_report()
    return lesson


def lessons_for_injection(limit: int | None = None) -> List[Dict[str, Any]]:
    settings = get_settings()
    if not settings.get("enabled", True) or not settings.get("auto_inject", True):
        return []
    max_items = int(limit if limit is not None else settings.get("max_injected", 3))
    rows = list(reversed(_self_fix_lessons()))
    rows.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at", "")), reverse=True)
    rows.sort(key=lambda r: 0 if r.get("priority") == "high" else 1)
    return rows[:max(0, max_items)]


def format_injection_block(limit: int | None = None) -> str:
    lessons = lessons_for_injection(limit=limit)
    if not lessons:
        return ""
    lines = ["## OpenCodeLIG 자가개선 지침", "같은 시행착오를 반복하지 않도록 우선 적용:"]
    for row in lessons:
        lines.append(f"- {str(row.get('body', '')).strip()[:220]}")
    return "\n".join(lines)


def render_report() -> Path:
    _ensure()
    errors = _self_errors()
    lessons = _self_fix_lessons()
    lines = [
        "# Self Improvement Report",
        "",
        f"- updated: `{now_iso()}`",
        f"- enabled: `{get_settings().get('enabled', True)}`",
        f"- errors: `{len(errors)}`",
        f"- lessons: `{len(lessons)}`",
        "",
        "## Active Lessons",
    ]
    if not lessons:
        lines.append("- 없음")
    for row in lessons[:20]:
        lines.append(f"- **{row.get('title')}**: {row.get('body')}")
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
        "errors": len(_self_errors()),
        "lessons": len(_self_fix_lessons()),
    }
