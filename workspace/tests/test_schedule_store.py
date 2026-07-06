# -*- coding: utf-8 -*-
"""Deterministic schedule store/date parser tests.

Run: py -3.11 tests\test_schedule_store.py
"""
from __future__ import annotations

import json
import os
import subprocess
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
    no_due_word = store.parse_due("언제까지인지 모르는 일", now=NOW)
    check("single-character weekday inside words is not a due date", no_due_word.get("ok") is False, str(no_due_word))

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

    cli_tmp = Path(tempfile.mkdtemp(prefix="schedule_cli_test_"))
    cli_env = dict(os.environ)
    cli_env["PYTHONUTF8"] = "1"
    cli_env["PYTHONIOENCODING"] = "utf-8"
    cli_env["LIG_SCHEDULE_DIR"] = str(cli_tmp / "schedule")
    cmd = ["py", "-3.11", str(Path(__file__).resolve().parents[1] / "agent_ops" / "agentops.py"), "schedule"]

    add = subprocess.run(cmd + ["add", "오늘 14시 진동시험 보고서 마감"],
                         cwd=str(Path(__file__).resolve().parents[1]), env=cli_env,
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    check("CLI add exits 0", add.returncode == 0 and "등록됨:" in add.stdout, add.stdout + add.stderr)
    today_cli = subprocess.run(cmd + ["today"], cwd=str(Path(__file__).resolve().parents[1]), env=cli_env,
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    check("CLI today shows fixed columns and item",
          today_cli.returncode == 0 and "ID" in today_cli.stdout and "진동시험 보고서 마감" in today_cli.stdout,
          today_cli.stdout + today_cli.stderr)
    check("CLI today uses displayed schedule id", "sch_0001" in today_cli.stdout, today_cli.stdout)
    done_cli = subprocess.run(cmd + ["done", "sch_0001"], cwd=str(Path(__file__).resolve().parents[1]), env=cli_env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    check("CLI done marks item", done_cli.returncode == 0 and "완료됨: sch_0001" in done_cli.stdout,
          done_cli.stdout + done_cli.stderr)
    bad_cli = subprocess.run(cmd + ["add", "언젠가 진동시험 보고서"], cwd=str(Path(__file__).resolve().parents[1]), env=cli_env,
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    check("CLI ambiguous add exits 2 with guidance",
          bad_cli.returncode == 2 and "기한을 인식하지 못했습니다" in (bad_cli.stdout + bad_cli.stderr),
          bad_cli.stdout + bad_cli.stderr)
    no_due_cli = subprocess.run(cmd + ["add", "언제까지인지 모르는 일"], cwd=str(Path(__file__).resolve().parents[1]),
                                env=cli_env, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=60)
    check("CLI no-due word with 일 exits 2",
          no_due_cli.returncode == 2 and "기한을 인식하지 못했습니다" in (no_due_cli.stdout + no_due_cli.stderr),
          no_due_cli.stdout + no_due_cli.stderr)
    title_cases = [
        ("금형 부품 검토 7월 8일까지", "금형 부품 검토"),
        ("수정사항 반영 내일까지", "수정사항 반영"),
        ("월간 보고 7월 10일까지 제출", "월간 보고 제출"),
    ]
    for idx, (raw, expected_title) in enumerate(title_cases, start=2):
        added = subprocess.run(cmd + ["add", raw], cwd=str(Path(__file__).resolve().parents[1]), env=cli_env,
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        check(f"CLI preserves title words case {idx}", added.returncode == 0 and expected_title in added.stdout,
              added.stdout + added.stderr)
    stored = json.loads((cli_tmp / "schedule" / "schedule.json").read_text(encoding="utf-8"))["items"]
    titles = [item["title"] for item in stored]
    check("CLI stored 금형 title intact", "금형 부품 검토" in titles, str(titles))
    check("CLI stored 수정사항 title intact", "수정사항 반영" in titles, str(titles))
    check("CLI stored 월간 title intact", "월간 보고 제출" in titles, str(titles))
    denied = subprocess.run(cmd + ["remove", "sch_0001"], input="n\n",
                            cwd=str(Path(__file__).resolve().parents[1]), env=cli_env,
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    check("CLI remove denial exits 3", denied.returncode == 3 and "삭제할까요? [y/N]" in denied.stdout,
          denied.stdout + denied.stderr)
    removed = subprocess.run(cmd + ["remove", "sch_0001", "--yes"],
                             cwd=str(Path(__file__).resolve().parents[1]), env=cli_env,
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    check("CLI remove --yes deletes item", removed.returncode == 0 and "삭제됨: sch_0001" in removed.stdout,
          removed.stdout + removed.stderr)
    outlook_env = dict(cli_env)
    outlook_env["LIG_OUTLOOK_COM_DISABLE"] = "1"
    outlook = subprocess.run(cmd + ["sync-outlook", "--days", "1"],
                             cwd=str(Path(__file__).resolve().parents[1]), env=outlook_env,
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    check("CLI sync-outlook absence exits 2 with guidance",
          outlook.returncode == 2 and "pywin32 미설치" in (outlook.stdout + outlook.stderr),
          outlook.stdout + outlook.stderr)

    print(f"\nALL {PASS} CHECKS PASSED (schedule store)")


if __name__ == "__main__":
    main()
