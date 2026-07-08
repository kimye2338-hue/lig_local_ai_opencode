# -*- coding: utf-8 -*-
"""WS-8 evaluation loop tests (self-scoring, append-only storage, no over-promotion).

Run: py -3.11 tests\test_evaluation_loop.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

# tmp 격리: 실제 USERDATA/diagnostics를 건드리지 않도록 import 전에 설정.
TMP = Path(tempfile.mkdtemp(prefix="agentops_eval_"))
os.environ["LIG_DIAG_DIR"] = str(TMP / "diag")

from agent_ops.evaluation_loop import (  # noqa: E402
    MIN_SAMPLES,
    append_evaluation,
    growth_report,
    route_preferences,
    score_run,
    _default_eval_path,
)

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def make_trace(**over) -> dict:
    trace = {
        "timestamp": "2026-07-08T12:00:00",
        "request": "테스트 요청",
        "routing": "keyword",
        "planner_mode": "keyword",
        "capabilities": [{"id": "file_ops", "confidence": "high"}],
        "selected_path": "tool_agent",
        "command": "agent",
        "policy": {"mode": "execute", "requires_confirmation": False},
        "effective_mode": "execute",
        "memory_hooks": ["_complete_activity fired: activity"],
        "verification": ["auto-route trace written"],
        "exit_code": 0,
        "outcome": "completed",
    }
    trace.update(over)
    return trace


def main() -> None:
    # (1) score_run: 성공/실패/ask_user/blocked에서 합리적 점수.
    ok_rec = score_run(make_trace())
    s = ok_rec["scores"]
    check("success run scores tool_success 1.0", s["tool_success"] == 1.0, str(s))
    check("success run has high route_confidence", s["route_confidence"] >= 0.8, str(s))
    check("success run has no user friction", s["user_friction"] == 0.0, str(s))
    check("all scores within 0..1",
          all(0.0 <= v <= 1.0 for v in s.values()), str(s))

    fail_rec = score_run(make_trace(exit_code=2, outcome="failed"))
    check("failed run scores tool_success 0.0",
          fail_rec["scores"]["tool_success"] == 0.0, str(fail_rec["scores"]))
    check("failed run keeps high learning_value (lesson worth keeping)",
          fail_rec["scores"]["learning_value"] >= 0.7, str(fail_rec["scores"]))

    ask_rec = score_run(make_trace(
        effective_mode="ask_user", outcome="needs_confirmation",
        policy={"mode": "ask_user", "requires_confirmation": True}))
    check("ask_user run reflects user friction",
          ask_rec["scores"]["user_friction"] >= 0.5, str(ask_rec["scores"]))
    check("ask_user run keeps high safety_margin",
          ask_rec["scores"]["safety_margin"] >= 0.8, str(ask_rec["scores"]))
    check("ask_user run tool_success stays neutral (nothing executed)",
          ask_rec["scores"]["tool_success"] == 0.5, str(ask_rec["scores"]))

    blocked_rec = score_run(make_trace(
        effective_mode="blocked", outcome="blocked",
        policy={"mode": "blocked", "requires_confirmation": False}))
    check("blocked run scores maximum safety_margin",
          blocked_rec["scores"]["safety_margin"] == 1.0, str(blocked_rec["scores"]))

    check("score_run is deterministic (pure)",
          score_run(make_trace()) == score_run(make_trace()))
    check("score_run uses trace timestamp (no clock dependency)",
          ok_rec["timestamp"] == "2026-07-08T12:00:00", ok_rec["timestamp"])
    check("score_run tolerates empty trace",
          isinstance(score_run({}), dict))

    # (2) append_evaluation: JSONL append-only 누적 (파괴 없음).
    eval_path = _default_eval_path()
    check("default eval path stays inside isolated LIG_DIAG_DIR",
          str(eval_path).startswith(str(TMP)), str(eval_path))
    append_evaluation(ok_rec)
    lines = eval_path.read_text(encoding="utf-8").splitlines()
    check("first append writes exactly one JSONL line", len(lines) == 1)
    append_evaluation(fail_rec)
    lines = eval_path.read_text(encoding="utf-8").splitlines()
    check("second append accumulates (no rewrite/truncate)", len(lines) == 2)
    check("first line survived untouched (append-only)",
          json.loads(lines[0])["outcome"] == "completed", lines[0])
    check("lines are valid json with score fields",
          all("scores" in json.loads(ln) for ln in lines))

    # (3) route_preferences: min_samples 미만 route는 선호로 승격 금지.
    pref_path = TMP / "prefs.jsonl"
    append_evaluation(score_run(make_trace(selected_path="lonely_route")), pref_path)
    for _ in range(MIN_SAMPLES):
        append_evaluation(score_run(make_trace(selected_path="steady_route")), pref_path)
    prefs = route_preferences(path=pref_path)
    check("single success is NOT promoted to a preference",
          "lonely_route" not in prefs["preferences"], str(prefs))
    check("single success is surfaced as insufficient sample",
          prefs["insufficient"].get("lonely_route") == 1, str(prefs))
    check("route with enough samples appears with avg+samples",
          prefs["preferences"].get("steady_route", {}).get("samples") == MIN_SAMPLES,
          str(prefs))
    check("preference avg is a 0..1 score",
          0.0 <= prefs["preferences"]["steady_route"]["avg_score"] <= 1.0, str(prefs))
    check("preferences declare themselves read-only signal",
          "policy unchanged" in prefs["note"], prefs["note"])

    # growth_report: 사람이 읽을 요약.
    report = growth_report(path=pref_path)
    check("growth report counts total runs",
          report["total_runs"] == MIN_SAMPLES + 1, str(report))
    check("growth report holds under-sampled routes (보류)",
          "lonely_route" in report["held_routes"], str(report))
    check("growth report lists promotion candidates only from sampled prefs",
          "lonely_route" not in report["promotion_candidates"], str(report))
    check("growth report tracks ask_user count",
          isinstance(report["ask_user_count"], int), str(report))

    # (4) 저장 실패에도 예외 미전파.
    blocker = TMP / "not_a_dir"
    blocker.write_text("file, not dir", encoding="utf-8")
    bad_path = blocker / "sub" / "evals.jsonl"  # 부모가 파일 → 생성 불가
    try:
        append_evaluation(ok_rec, bad_path)
        check("append_evaluation swallows storage failure", True)
    except Exception as exc:  # pragma: no cover
        check("append_evaluation swallows storage failure", False, repr(exc))
    check("unreadable path yields empty preferences (no crash)",
          route_preferences(path=bad_path)["preferences"] == {})

    print(f"\nALL {PASS} CHECKS PASSED (evaluation loop)")


if __name__ == "__main__":
    main()
