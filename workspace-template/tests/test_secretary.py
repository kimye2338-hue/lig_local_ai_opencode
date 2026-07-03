# -*- coding: utf-8 -*-
"""Tests for morning briefing and reminder launchers.

Run: py -3.11 tests\test_secretary.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

WS_TEMPLATE = Path(__file__).resolve().parents[1]
AGENTOPS = WS_TEMPLATE / "agent_ops" / "agentops.py"
PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def env_for(case: str) -> tuple[Path, Path, dict]:
    tmp = Path(tempfile.mkdtemp(prefix=f"secretary_{case}_"))
    ws = tmp / "작업공간"
    env = dict(os.environ)
    env.update({
        "AGENTOPS_ROOT": str(ws),
        "LIG_SCHEDULE_DIR": str(tmp / "schedule"),
        "LIG_AUDIT_DIR": str(tmp / "audit"),
        "LIG_BRIEFING_NOW": "2026-07-04 08:30",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    return tmp, ws, env


def run_briefing(env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(["py", "-3.11", str(AGENTOPS), "briefing"],
                          cwd=str(WS_TEMPLATE), env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=120)


def run_weekly(env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(["py", "-3.11", str(AGENTOPS), "weekly"],
                          cwd=str(WS_TEMPLATE), env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=120)


def seed_schedule(env: dict) -> None:
    import importlib
    sys.path.insert(0, str(WS_TEMPLATE))
    old_dir = os.environ.get("LIG_SCHEDULE_DIR")
    try:
        os.environ["LIG_SCHEDULE_DIR"] = env["LIG_SCHEDULE_DIR"]
        from agent_ops import schedule_store
        importlib.reload(schedule_store)
        schedule_store.add("오늘 설계 리뷰", "2026-07-04 10:00", now=None)
        schedule_store.add("치수 보고서 마감", "2026-07-06", now=None)
        schedule_store.add("지난 시험 follow-up", "2026-07-02", now=None)
    finally:
        if old_dir is None:
            os.environ.pop("LIG_SCHEDULE_DIR", None)
        else:
            os.environ["LIG_SCHEDULE_DIR"] = old_dir


def seed_actions_and_audit(ws: Path, env: dict) -> None:
    actions = ws / "agent_ops" / "results" / "artifacts" / "run1" / "액션아이템.md"
    actions.parent.mkdir(parents=True, exist_ok=True)
    actions.write_text(
        "# 액션아이템\n\n| 상태 | 항목 |\n|---|---|\n| 대기 | 결재 요청 확인 |\n| 완료 | 제외 항목 |\n",
        encoding="utf-8")
    audit = Path(env["LIG_AUDIT_DIR"]) / "audit.jsonl"
    audit.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"ts": "2026-07-03T09:00:00", "verdict": "approved"},
        {"ts": "2026-07-03T10:00:00", "verdict": "failed"},
        {"ts": "2026-07-02T10:00:00", "verdict": "failed"},
    ]
    audit.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                     encoding="utf-8")


def seed_weekly_fixtures(ws: Path, env: dict) -> None:
    seed_schedule(env)
    import importlib
    sys.path.insert(0, str(WS_TEMPLATE))
    old_dir = os.environ.get("LIG_SCHEDULE_DIR")
    try:
        os.environ["LIG_SCHEDULE_DIR"] = env["LIG_SCHEDULE_DIR"]
        from agent_ops import schedule_store
        importlib.reload(schedule_store)
        schedule_store.mark_done(1)
        schedule_store.mark_done(3)
    finally:
        if old_dir is None:
            os.environ.pop("LIG_SCHEDULE_DIR", None)
        else:
            os.environ["LIG_SCHEDULE_DIR"] = old_dir
    audit = Path(env["LIG_AUDIT_DIR"]) / "audit.jsonl"
    audit.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"ts": "2026-07-01T09:00:00", "kind": "work", "task": "시험 결과 보고서 작성", "verdict": "approved"},
        {"ts": "2026-07-02T10:00:00", "kind": "schedule", "task": "일정 등록", "verdict": "approved"},
        {"ts": "2026-06-20T10:00:00", "kind": "old", "task": "오래된 작업", "verdict": "approved"},
    ]
    audit.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                     encoding="utf-8")
    art = ws / "agent_ops" / "results" / "artifacts" / "run-week" / "문서.md"
    art.parent.mkdir(parents=True, exist_ok=True)
    art.write_text("# 시험 결과 보고서\n", encoding="utf-8")


def test_briefing_with_fixtures() -> None:
    tmp, ws, env = env_for("fixtures")
    seed_schedule(env)
    seed_actions_and_audit(ws, env)
    r = run_briefing(env)
    out = r.stdout + r.stderr
    check("briefing exits 0", r.returncode == 0, out)
    report = ws / "agent_ops" / "results" / "reports" / "briefing_20260704.md"
    check("briefing report created", report.exists(), out)
    body = report.read_text(encoding="utf-8")
    for section in ("## 오늘 일정", "## 이번 주 일정", "## 마감 임박", "## 미완료 액션아이템", "## 어제 audit 요약"):
        check(f"briefing has section {section}", section in body, body)
    check("today schedule reflected", "오늘 설계 리뷰" in body, body)
    check("due soon schedule reflected", "치수 보고서 마감" in body and "지난 시험 follow-up" in body, body)
    check("overdue is emphasized", "**OVERDUE**" in body, body)
    check("pending action reflected with source", "결재 요청 확인" in body and "출처: 액션아이템.md" in body, body)
    check("yesterday audit summary counted", "실행 2건 / 실패 1건" in body, body)
    check("console prints briefing", "Morning Briefing 2026-07-04" in out and "브리핑 저장:" in out, out)


def test_empty_briefing_says_none() -> None:
    _tmp, ws, env = env_for("empty")
    r = run_briefing(env)
    out = r.stdout + r.stderr
    check("empty briefing exits 0", r.returncode == 0, out)
    body = (ws / "agent_ops" / "results" / "reports" / "briefing_20260704.md").read_text(encoding="utf-8")
    check("empty sections say none", body.count("없음") >= 4, body)
    check("empty audit says no records", "audit 기록 없음" in body or "어제 audit 기록 없음" in body, body)


def test_weekly_report_with_fixtures() -> None:
    _tmp, ws, env = env_for("weekly")
    seed_weekly_fixtures(ws, env)
    r = run_weekly(env)
    out = r.stdout + r.stderr
    check("weekly exits 0", r.returncode == 0, out)
    report = ws / "agent_ops" / "results" / "reports" / "weekly_20260704.md"
    check("weekly report created", report.exists(), out)
    body = report.read_text(encoding="utf-8")
    for section in ("## 수행 업무", "## 완료 일정", "## 다음 주 예정", "## 생성 산출물"):
        check(f"weekly has section {section}", section in body, body)
    check("weekly cites all three sources",
          "audit:" in body and "schedule:" in body and "artifacts:" in body, body)
    check("weekly reflects audit tasks", "시험 결과 보고서 작성" in body and "일정 등록" in body, body)
    check("weekly reflects done schedules", "오늘 설계 리뷰" in body and "지난 시험 follow-up" in body, body)
    check("weekly reflects next week open schedule", "치수 보고서 마감" in body, body)
    check("weekly reflects generated artifacts", "run-week" in body and "문서.md" in body, body)
    check("weekly is clearly a draft", "TODO: 정성 성과/이슈는 직접 보완" in body, body)
    check("console prints weekly report", "Weekly Report Draft 2026-07-04" in out and "주간보고 저장:" in out, out)


def test_empty_weekly_says_none() -> None:
    _tmp, ws, env = env_for("weekly_empty")
    r = run_weekly(env)
    out = r.stdout + r.stderr
    check("empty weekly exits 0", r.returncode == 0, out)
    body = (ws / "agent_ops" / "results" / "reports" / "weekly_20260704.md").read_text(encoding="utf-8")
    check("empty weekly sections say none", body.count("없음") >= 4, body)
    check("empty weekly still cites sources", "audit:" in body and "schedule:" in body and "artifacts:" in body, body)
    check("empty weekly keeps draft TODO", "TODO: 정성 성과/이슈는 직접 보완" in body, body)


def test_reminder_bats_are_confirm_first() -> None:
    install = (WS_TEMPLATE / "launch" / "install-reminder.bat").read_text(encoding="ascii")
    uninstall = (WS_TEMPLATE / "launch" / "uninstall-reminder.bat").read_text(encoding="ascii")
    briefing = (WS_TEMPLATE / "launch" / "briefing.bat").read_text(encoding="ascii")
    check("briefing bat calls briefing command", "agentops.py briefing" in briefing, briefing)
    check("install bat prints schtasks create", "schtasks /Create" in install and "echo %SCHTASKS_CMD%" in install, install)
    check("install bat asks before running", "set /p ANSWER" in install and 'not "%ANSWER%"=="y"' in install, install)
    check("uninstall bat asks before running", "schtasks /Delete" in uninstall and "set /p ANSWER" in uninstall, uninstall)


def main() -> None:
    test_briefing_with_fixtures()
    test_empty_briefing_says_none()
    test_weekly_report_with_fixtures()
    test_empty_weekly_says_none()
    test_reminder_bats_are_confirm_first()
    print(f"\nALL {PASS} CHECKS PASSED (secretary briefing)")


if __name__ == "__main__":
    main()
