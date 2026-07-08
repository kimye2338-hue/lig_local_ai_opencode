# -*- coding: utf-8 -*-
"""WS-7 execution policy engine tests.

Run: py -3.11 tests\test_auto_policy.py
"""
from __future__ import annotations

import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

from agent_ops.auto_policy import MODE_SEVERITY, choose_execution_policy  # noqa: E402

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def policy(request: str, *, path: str = "artifact", command: str = "work",
           pending=None, safety=None):
    hint = {"selected_path": path, "command": command, "reason": "test"}
    ctx = {"pending": list(pending or [])}
    return choose_execution_policy(request, [], ctx, safety, hint)


def main() -> None:
    # (1) reversible work executes without asking
    p = policy("진동시험 결과 보고서 작성해줘", path="artifact", command="work",
               safety={"decision": "review_required", "risk": "review_required",
                       "matched_danger": []})
    check("reversible report -> execute", p["mode"] == "execute", str(p))
    check("reversible report needs no confirmation",
          p["requires_confirmation"] is False, str(p))
    p = policy("지난주 회의 내용 회상해줘", path="memory_wiki", command="recall",
               safety={"decision": "safe", "risk": "safe", "matched_danger": []})
    check("recall -> execute", p["mode"] == "execute", str(p))
    p = policy("이 작업 계획 세워줘", path="plan_only", command="plan")
    check("plan route -> plan_only", p["mode"] == "plan_only", str(p))

    # (2) hard-to-undo signals ask the user
    p = policy("임시 파일 전부 삭제해줘", path="tool_agent", command="agent",
               safety={"decision": "blocked", "risk": "review_required",
                       "matched_danger": ["삭제"]})
    check("file delete -> ask_user", p["mode"] == "ask_user", str(p))
    check("file delete requires confirmation",
          p["requires_confirmation"] is True, str(p))
    check("ask_user leaves a question for the trace", bool(p["question"]), str(p))
    p = policy("엑셀 원본에 저장까지 해줘", path="tool_agent", command="agent",
               safety={"decision": "blocked", "risk": "review_required",
                       "matched_danger": ["저장"]})
    check("app real save -> ask_user", p["mode"] == "ask_user", str(p))
    p = policy("기본 모델 변경해줘", path="tool_agent", command="agent")
    check("model default change -> ask_user", p["mode"] == "ask_user", str(p))
    p = policy("결과 메일 발송해줘", path="tool_agent", command="agent",
               safety={"decision": "blocked", "risk": "review_required",
                       "matched_danger": ["발송"]})
    check("external send -> ask_user", p["mode"] == "ask_user", str(p))

    # (3) safety demotion is one-way conservative
    p = policy("작업 폴더 정리해줘", path="tool_agent", command="agent",
               safety={"decision": "deny", "risk": "high"})
    check("safety deny -> blocked", p["mode"] == "blocked", str(p))
    check("blocked never asks confirmation instead",
          p["requires_confirmation"] is False, str(p))
    check("blocked keeps safe fallback", p["fallback"] == "plan_only", str(p))
    p = policy("디스크 초기화해줘", path="tool_agent", command="agent",
               safety={"decision": "blocked", "risk": "review_required",
                       "matched_danger": ["초기화"]})
    check("irreversible term -> blocked", p["mode"] == "blocked", str(p))
    # safety=safe can never promote an ask_user decision back to execute
    p = policy("임시 파일 전부 삭제해줘", path="tool_agent", command="agent",
               safety={"decision": "safe", "risk": "safe", "matched_danger": []})
    check("safe classification cannot promote delete to execute",
          p["mode"] == "ask_user", str(p))
    # and a deny floor overrides an execute base (never the other direction)
    p = policy("보고서 작성해줘", path="artifact", command="work",
               safety={"decision": "deny", "risk": "high"})
    check("deny floor demotes even reversible base",
          p["mode"] == "blocked", str(p))
    check("severity ladder is ordered",
          MODE_SEVERITY["execute"] < MODE_SEVERITY["plan_only"]
          < MODE_SEVERITY["ask_user"] < MODE_SEVERITY["blocked"])

    # (4) pending app/tool prerequisites -> plan_only (not ask_user)
    p = policy("크롬으로 회사 포털 확인해줘", path="tool_agent", command="agent",
               pending=["real browser validation pending: 실제 Chrome 제어 검증"])
    check("pending tool route -> plan_only", p["mode"] == "plan_only", str(p))
    check("pending does not ask the user",
          p["requires_confirmation"] is False, str(p))

    # (5) no ask_user spam: plain lookups/registrations stay quiet
    p = policy("메모 파일 읽어줘", path="tool_agent", command="agent",
               safety={"decision": "review_required", "risk": "review_required",
                       "matched_danger": []})
    check("simple read -> execute", p["mode"] == "execute", str(p))
    p = policy("2026-07-10까지 보고서 마감 일정 등록해줘", path="command_native",
               command="schedule_add",
               safety={"decision": "blocked", "risk": "review_required",
                       "matched_danger": ["등록", "마감"]})
    check("internal schedule add stays execute despite keyword-tier safety",
          p["mode"] == "execute", str(p))
    p = policy("위키 정리해줘", path="memory_wiki", command="wiki",
               safety={"decision": "blocked", "risk": "review_required",
                       "matched_danger": ["정리"]})
    check("wiki curation stays execute", p["mode"] == "execute", str(p))

    # deterministic pure function
    a = policy("결과 메일 발송해줘", path="tool_agent", command="agent")
    b = policy("결과 메일 발송해줘", path="tool_agent", command="agent")
    check("policy is deterministic", a == b, f"{a} != {b}")

    print(f"\nALL {PASS} CHECKS PASSED (auto policy)")


if __name__ == "__main__":
    main()
