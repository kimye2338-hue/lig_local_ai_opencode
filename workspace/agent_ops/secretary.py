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


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _within_last_days(day: datetime | None, now: datetime, days: int = 7) -> bool:
    if day is None:
        return False
    start = (now - timedelta(days=days)).date()
    return start <= day.date() <= now.date()


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
    if not (today or week or due_soon):
        lines += ["> 일정이 비어 있습니다 — AI비서 메뉴의 [일정 추가]로 등록하거나 "
                  "[Outlook 일정 가져오기]로 동기화하세요.", ""]
    # 오늘의 복습 — 오래된 지식 1개를 결정적으로 회전(지식책과 동일 규칙, 일 단위)
    try:
        from agent_ops.knowledge_book import review_picks, _load_entries
        picks = review_picks(_load_entries(), current, limit=3)
        if picks:
            pick = picks[current.toordinal() % len(picks)]
            lines += ["## 오늘의 복습",
                      f"- {pick.get('title')}: {str(pick.get('body', ''))[:160]}", ""]
    except Exception:  # noqa: BLE001 - 복습 실패가 브리핑을 막으면 안 된다
        pass
    text = "\n".join(lines)
    path = RESULTS / "reports" / f"briefing_{current.strftime('%Y%m%d')}.md"
    atomic_write_text(path, text)
    return path, text


def _weekly_audit_rows(now: datetime) -> tuple[list[str], Path]:
    path = _audit_path()
    if not path.exists():
        return [], path
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        ts = _parse_ts(row.get("ts"))
        if not _within_last_days(ts, now):
            continue
        rows.append(row)
    if not rows:
        return [], path
    by_kind: dict[str, int] = {}
    tasks: list[str] = []
    for row in rows:
        kind = str(row.get("kind") or "unknown")
        by_kind[kind] = by_kind.get(kind, 0) + 1
        task = str(row.get("task") or "").strip()
        if task and task not in tasks:
            tasks.append(task[:80])
    lines = [f"- 총 {len(rows)}건: " + ", ".join(f"{k} {v}건" for k, v in sorted(by_kind.items()))]
    for task in tasks[:5]:
        lines.append(f"- 대표 task: {task}")
    return lines, path


def _weekly_done_schedule(now: datetime) -> list[str]:
    rows = []
    for item in schedule_store.list_items("all", now=now):
        if item.get("status") != "done":
            continue
        due = _due_datetime(item)
        if not _within_last_days(due, now):
            continue
        rows.append(f"- {item.get('due', '')} [{item.get('category', '기타')}] {item.get('title', '')}")
    return rows


def _weekly_next_schedule(now: datetime) -> list[str]:
    end = now + timedelta(days=7)
    rows = []
    for item in schedule_store.list_items("all", now=now):
        if item.get("status") != "open":
            continue
        due = _due_datetime(item)
        if due is None or not (now.date() <= due.date() <= end.date()):
            continue
        rows.append(f"- {item.get('due', '')} [{item.get('category', '기타')}] {item.get('title', '')}")
    return rows


def _weekly_artifacts(now: datetime) -> tuple[list[str], Path]:
    root = RESULTS / "artifacts"
    if not root.exists():
        return [], root
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            continue
        if _within_last_days(mtime, now):
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = Path(path.name)
            files.append(str(rel))
    if not files:
        return [], root
    lines = [f"- 생성/수정 파일 {len(files)}개"]
    for name in files[:8]:
        lines.append(f"- 대표 산출물: {name}")
    return lines, root


def build_weekly_report(now: datetime | None = None) -> tuple[Path, str]:
    current = now or _briefing_now()
    audit_lines, audit_path = _weekly_audit_rows(current)
    done_lines = _weekly_done_schedule(current)
    next_lines = _weekly_next_schedule(current)
    artifact_lines, artifact_root = _weekly_artifacts(current)
    schedule_path = schedule_store.schedule_path()
    date_label = current.strftime("%Y-%m-%d")
    lines = [
        f"# Weekly Report Draft {date_label}",
        "",
        "- 상태: locally generated draft — 기록 기반 초안입니다.",
        "- 자료 원천:",
        f"  - audit: `{audit_path}`",
        f"  - schedule: `{schedule_path}`",
        f"  - artifacts: `{artifact_root}`",
        "",
        "## 수행 업무",
        *(audit_lines or ["없음"]),
        "",
        "## 완료 일정",
        *(done_lines or ["없음"]),
        "",
        "## 다음 주 예정",
        *(next_lines or ["없음"]),
        "",
        "## 생성 산출물",
        *(artifact_lines or ["없음"]),
        "",
        "## 보완 필요",
        "TODO: 정성 성과/이슈는 직접 보완",
        "",
    ]
    text = "\n".join(lines)
    path = RESULTS / "reports" / f"weekly_{current.strftime('%Y%m%d')}.md"
    atomic_write_text(path, text)
    return path, text
