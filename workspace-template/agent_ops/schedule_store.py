# -*- coding: utf-8 -*-
"""Deterministic schedule storage and Korean due-date parsing."""
from __future__ import annotations

import os
import json
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .core import atomic_write_json, now as now_text

CATEGORIES = {"회의", "보고", "시험", "개인", "기타"}
SOURCES = {"manual", "mail", "meeting"}
QUESTION = "날짜를 다시 말씀해 주세요 (예: 내일 오후 3시, 금요일 14시, 7월 15일 09:30)"
WEEKDAYS = {
    "월요일": 0,
    "화요일": 1,
    "수요일": 2,
    "목요일": 3,
    "금요일": 4,
    "토요일": 5,
    "일요일": 6,
}
SHORT_WEEKDAYS = {
    "월": 0,
    "화": 1,
    "수": 2,
    "목": 3,
    "금": 4,
    "토": 5,
    "일": 6,
}
CATEGORY_KEYWORDS = {
    "회의": ("회의", "미팅", "meet", "meeting"),
    "보고": ("보고", "제출", "마감", "report"),
    "시험": ("시험", "테스트", "실험", "test"),
    "개인": ("개인", "병원", "휴가", "운동"),
}


def schedule_dir() -> Path:
    return Path(os.environ.get("LIG_SCHEDULE_DIR") or (Path.home() / "OpenCodeLIG_USERDATA" / "schedule"))


def schedule_path() -> Path:
    return schedule_dir() / "schedule.json"


def _coerce_now(value: Optional[datetime]) -> datetime:
    return value if value is not None else datetime.now()


def _load() -> Dict[str, Any]:
    path = schedule_path()
    if not path.exists():
        return {"items": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"items": []}
    if isinstance(data, list):
        return {"items": data}
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data
    return {"items": []}


def _save(data: Dict[str, Any]) -> None:
    path = schedule_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    atomic_write_json(path, data)


def _parse_time(text: str) -> tuple[Optional[tuple[int, int]], str]:
    cleaned = text
    ampm = None
    if "오전" in cleaned:
        ampm = "am"
        cleaned = cleaned.replace("오전", " ")
    if "오후" in cleaned:
        ampm = "pm"
        cleaned = cleaned.replace("오후", " ")
    m = re.search(r"(\d{1,2})\s*:\s*(\d{2})", cleaned)
    if not m:
        m = re.search(r"(\d{1,2})\s*시", cleaned)
    if not m:
        return None, cleaned
    hour = int(m.group(1))
    minute = int(m.group(2)) if m.lastindex and m.lastindex >= 2 and m.group(2) else 0
    if hour > 23 or minute > 59:
        return None, cleaned
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    cleaned = (cleaned[:m.start()] + " " + cleaned[m.end():]).strip()
    return (hour, minute), cleaned


def _format_due(day: datetime, clock: Optional[tuple[int, int]]) -> str:
    if clock is None:
        return day.strftime("%Y-%m-%d")
    return day.replace(hour=clock[0], minute=clock[1], second=0, microsecond=0).strftime("%Y-%m-%d %H:%M")


def _weekday_date(base: datetime, target: int, next_week: bool = False) -> datetime:
    delta = (target - base.weekday()) % 7
    if next_week:
        delta += 7
    return base + timedelta(days=delta)


def _future_month_day(base: datetime, month: int, day: int) -> Optional[datetime]:
    try:
        candidate = base.replace(month=month, day=day)
    except ValueError:
        return None
    if candidate.date() < base.date():
        try:
            candidate = candidate.replace(year=base.year + 1)
        except ValueError:
            return None
    return candidate


def parse_due(text: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    base = _coerce_now(now)
    raw = (text or "").strip()
    if not raw or raw in {"다음에", "언젠가", "나중에"}:
        return {"ok": False, "question": QUESTION}
    clock, date_text = _parse_time(raw)
    compact = re.sub(r"\s+", "", date_text)
    day: Optional[datetime] = None

    relative_days = {"오늘": 0, "내일": 1, "모레": 2, "글피": 3}
    for key, offset in relative_days.items():
        if key in compact:
            day = base + timedelta(days=offset)
            break

    if day is None:
        m = re.search(r"(\d+)(?:일|일\s*)후", date_text)
        if m:
            day = base + timedelta(days=int(m.group(1)))
    if day is None:
        m = re.search(r"(\d+)\s*주(?:일)?\s*후", date_text)
        if m:
            day = base + timedelta(days=7 * int(m.group(1)))

    if day is None:
        m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_text)
        if m:
            try:
                day = base.replace(year=int(m.group(1)), month=int(m.group(2)), day=int(m.group(3)))
            except ValueError:
                day = None
    if day is None:
        m = re.search(r"(\d{1,2})/(\d{1,2})", date_text)
        if m:
            day = _future_month_day(base, int(m.group(1)), int(m.group(2)))
    if day is None:
        m = re.search(r"(\d{1,2})월\s*(\d{1,2})일", date_text)
        if m:
            day = _future_month_day(base, int(m.group(1)), int(m.group(2)))

    if day is None:
        next_week = "다음주" in compact or "다음 주" in date_text
        for name, target in WEEKDAYS.items():
            if name in compact:
                day = _weekday_date(base, target, next_week=next_week)
                break
    if day is None:
        short = re.search(r"(이번주|다음주|다음\s+주|오는)\s*([월화수목금토일])(?:\s|$)", date_text)
        if short:
            prefix = re.sub(r"\s+", "", short.group(1))
            day = _weekday_date(base, SHORT_WEEKDAYS[short.group(2)], next_week=prefix == "다음주")

    if day is None:
        return {"ok": False, "question": QUESTION}
    return {"ok": True, "due": _format_due(day, clock)}


def infer_category(title: str, category: Optional[str] = None) -> str:
    if category in CATEGORIES:
        return str(category)
    lowered = (title or "").lower()
    for cat, words in CATEGORY_KEYWORDS.items():
        if any(word.lower() in lowered for word in words):
            return cat
    return "기타"


def _next_id(items: List[Dict[str, Any]]) -> int:
    ids = [int(item.get("id", 0)) for item in items if str(item.get("id", "")).isdigit()]
    return (max(ids) + 1) if ids else 1


def add(title: str, due_text: str, category: Optional[str] = None,
        source: str = "manual", now: Optional[datetime] = None) -> Dict[str, Any]:
    parsed = parse_due(due_text, now=now)
    if not parsed.get("ok"):
        return parsed
    data = _load()
    items = data["items"]
    item = {
        "id": _next_id(items),
        "title": str(title or "").strip(),
        "due": parsed["due"],
        "category": infer_category(title, category),
        "status": "open",
        "source": source if source in SOURCES else "manual",
        "created": now_text(),
    }
    items.append(item)
    _save(data)
    return {"ok": True, "item": item}


def _due_date(item: Dict[str, Any]) -> datetime:
    text = str(item.get("due", ""))
    fmt = "%Y-%m-%d %H:%M" if " " in text else "%Y-%m-%d"
    return datetime.strptime(text, fmt)


def list_items(when: str = "all", now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    base = _coerce_now(now)
    items = list(_load()["items"])
    if when == "all":
        return sorted(items, key=lambda item: (item.get("due", ""), item.get("id", 0)))
    result = []
    for item in items:
        due = _due_date(item)
        is_open = item.get("status") == "open"
        if when == "today" and due.date() == base.date():
            result.append(item)
        elif when == "week" and base.date() <= due.date() <= (base + timedelta(days=6)).date():
            result.append(item)
        elif when == "overdue" and is_open and due.date() < base.date():
            result.append(item)
    return sorted(result, key=lambda item: (item.get("due", ""), item.get("id", 0)))


def mark_done(id: int) -> Dict[str, Any]:
    data = _load()
    for item in data["items"]:
        if item.get("id") == id:
            item["status"] = "done"
            _save(data)
            return {"ok": True, "item": item}
    return {"ok": False, "error": "schedule item not found"}


def remove(id: int) -> Dict[str, Any]:
    data = _load()
    before = len(data["items"])
    data["items"] = [item for item in data["items"] if item.get("id") != id]
    if len(data["items"]) == before:
        return {"ok": False, "error": "schedule item not found"}
    _save(data)
    return {"ok": True, "removed": id}
