# -*- coding: utf-8 -*-
"""Morning briefing helpers for schedule, actions, and audit summaries."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from .core import RESULTS, atomic_write_text
from . import schedule_store


def _briefing_now() -> datetime:
    raw = os.environ.get("LIG_BRIEFING_NOW", "").strip()
    if raw:
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                pass
    return datetime.now()


def _due_datetime(item: dict[str, Any]) -> datetime | None:
    text = str(item.get("due", ""))
    fmt = "%Y-%m-%d %H:%M" if " " in text else "%Y-%m-%d"
    try:
        return datetime.strptime(text, fmt)
    except ValueError:
        return None


def _format_schedule_rows(items: Iterable[dict[str, Any]], now: datetime,
                          overdue_label: bool = False) -> list[str]:
    rows = []
    for item in items:
        due = _due_datetime(item)
        if due is None:
            due_label = str(item.get("due", ""))
            marker = ""
        else:
            due_label = due.strftime("%Y-%m-%d %H:%M" if " " in str(item.get("due", "")) else "%Y-%m-%d")
            marker = " **OVERDUE**" if overdue_label and due.date() < now.date() and item.get("status") == "open" else ""
        rows.append(f"- {due_label}{marker} [{item.get('category', '기타')}] {item.get('title', '')}")
    return rows or ["없음"]


def due_soon_items(now: datetime, days: int = 3) -> list[dict[str, Any]]:
    end = now + timedelta(days=days)
    items = []
    for item in schedule_store.list_items("all", now=now):
        if item.get("status") != "open":
            continue
        due = _due_datetime(item)
        if due is None:
            continue
        if due.date() <= end.date():
            items.append(item)
    return sorted(items, key=lambda item: (item.get("due", ""), item.get("id", 0)))


def collect_action_items(limit_per_file: int = 5) -> list[str]:
    root = RESULTS / "artifacts"
    if not root.exists():
        return []
    rows: list[str] = []
    for path in sorted(root.rglob("액션아이템.md")):
        try:
            path.relative_to(root)
        except ValueError:
            continue
        picked = 0
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            text = line.strip()
            if not text or "대기" not in text:
                continue
            rows.append(f"- {text} (출처: {path.name})")
            picked += 1
            if picked >= limit_per_file:
                break
    return rows


def _audit_path() -> Path:
    from . import audit
    return Path(os.environ.get("LIG_AUDIT_DIR") or audit.AUDIT_DIR) / audit.AUDIT_FILE


def audit_yesterday_summary(now: datetime) -> str:
    path = _audit_path()
    if not path.exists():
        return "audit 기록 없음"
    target = (now - timedelta(days=1)).date()
    total = 0
    failed = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        ts = str(row.get("ts", ""))
        try:
            row_date = datetime.fromisoformat(ts).date()
        except ValueError:
            row_date = None
        if row_date != target:
            continue
        total += 1
        verdict = str(row.get("verdict", "")).lower()
        if verdict in {"failed", "error", "denied"}:
            failed += 1
    return f"실행 {total}건 / 실패 {failed}건" if total else "어제 audit 기록 없음"


def build_briefing(now: datetime | None = None) -> tuple[Path, str]:
    current = now or _briefing_now()
    today = schedule_store.list_items("today", now=current)
    week = schedule_store.list_items("week", now=current)
    due_soon = due_soon_items(current)
    actions = collect_action_items()
    audit_summary = audit_yesterday_summary(current)

    date_label = current.strftime("%Y-%m-%d")
    lines = [
        f"# Morning Briefing {date_label}",
        "",
        "## 오늘 일정",
        *_format_schedule_rows(today, current),
        "",
        "## 이번 주 일정",
        *_format_schedule_rows(week, current),
        "",
        "## 마감 임박",
        *_format_schedule_rows(due_soon, current, overdue_label=True),
        "",
        "## 미완료 액션아이템",
        *(actions or ["없음"]),
        "",
        "## 어제 audit 요약",
        audit_summary,
        "",
    ]
    text = "\n".join(lines)
    path = RESULTS / "reports" / f"briefing_{current.strftime('%Y%m%d')}.md"
    atomic_write_text(path, text)
    return path, text
