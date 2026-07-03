# -*- coding: utf-8 -*-
"""Deterministic schedule store/date parser tests.

Run: py -3.11 tests\test_schedule_store.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="schedule_store_test_"))
os.environ["LIG_SCHEDULE_DIR"] = str(tmp / "schedule")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_ops import schedule_store as store  # noqa: E402

PASS = 0
NOW = datetime(2026, 7, 3, 10, 0)  # Friday


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def due(text: str) -> str:
    result = store.parse_due(text, now=NOW)
    check(f"parse ok: {text}", result.get("ok") is True, str(result))
    return result["due"]


def main() -> None:
    check("today parses", due("오늘") == "2026-07-03")
    check("tomorrow parses", due("내일") == "2026-07-04")
    check("day after tomorrow parses", due("모레") == "2026-07-05")
    check("three days ahead parses", due("글피") == "2026-07-06")
    check("same weekday parses today", due("금요일") == "2026-07-03")
    check("this week weekday parses today", due("이번주 금요일") == "2026-07-03")
    check("past weekday rolls forward", due("화요일") == "2026-07-07")
    check("next week weekday parses", due("다음주 화요일") == "2026-07-14")
    check("relative days parse", due("3일 후") == "2026-07-06")
    check("relative one week parses", due("1주일 후") == "2026-07-10")
    check("relative weeks parse", due("2주 후") == "2026-07-17")
    check("month day parses", due("7월 15일") == "2026-07-15")
    check("iso date parses", due("2026-07-15") == "2026-07-15")
    check("slash date future-adjusts year", due("12/25") == "2026-12-25")
    check("month day past rolls next year", due("1월 2일") == "2027-01-02")
    check("weekday hour parses", due("금요일 14시") == "2026-07-03 14:00")
    check("tomorrow afternoon parses", due("내일 오후 3시") == "2026-07-04 15:00")
    check("month day time parses", due("7월 15일 09:30") == "2026-07-15 09:30")

    ambiguous = store.parse_due("언젠가", now=NOW)
    check("ambiguous asks question", ambiguous.get("ok") is False and "날짜를 다시" in ambiguous.get("question", ""))
    empty = store.parse_due("", now=NOW)
    check("empty asks question", empty.get("ok") is False and "예:" in empty.get("question", ""))

    first = store.add("금요일 14시 진동시험 보고서 마감", "금요일 14시", now=NOW)
    check("add returns item", first.get("ok") and first["item"]["id"] == 1, str(first))
    check("category inferred as report", first["item"]["category"] == "보고", str(first))
    second = store.add("팀 회의", "내일 오전 9시", source="meeting", now=NOW)
    check("second id increments", second.get("ok") and second["item"]["id"] == 2, str(second))
    third = store.add("어제 마감", "2026-07-02", now=NOW)
    check("absolute past date is allowed with explicit year", third.get("ok"), str(third))

    today = store.list_items("today", now=NOW)
    check("today query includes first item", [item["id"] for item in today] == [1], str(today))
    week = store.list_items("week", now=NOW)
    check("week query includes today and tomorrow", {item["id"] for item in week} == {1, 2}, str(week))
    overdue = store.list_items("overdue", now=NOW)
    check("overdue query includes past open item", [item["id"] for item in overdue] == [3], str(overdue))

    done = store.mark_done(3)
    check("mark_done transitions status", done.get("ok") and done["item"]["status"] == "done", str(done))
    check("done item not overdue", store.list_items("overdue", now=NOW) == [])
    removed = store.remove(2)
    check("remove deletes item", removed.get("ok") and {item["id"] for item in store.list_items()} == {1, 3})

    path = store.schedule_path()
    body = json.loads(path.read_text(encoding="utf-8"))
    check("stored schema is object with items", isinstance(body, dict) and isinstance(body.get("items"), list), str(body))
    check("backup file exists after updates", path.with_suffix(path.suffix + ".bak").exists(), str(path))
    check("missing item returns ok false", not store.mark_done(999).get("ok") and not store.remove(999).get("ok"))
    check("invalid due add asks question and does not save", not store.add("애매한 일정", "다음에", now=NOW).get("ok"))
    check("no external date parser dependency", "dateutil" not in sys.modules)

    print(f"\nALL {PASS} CHECKS PASSED (schedule store)")


if __name__ == "__main__":
    main()
