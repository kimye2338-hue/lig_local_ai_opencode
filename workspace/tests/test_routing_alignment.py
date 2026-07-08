# -*- coding: utf-8 -*-
"""Capability id is the shared source for tools, skills, and context hints."""
from __future__ import annotations

import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

from agent_ops import capabilities as CAP  # noqa: E402
from agent_ops import skill_router as SR  # noqa: E402
from agent_ops import tool_dispatch as TD  # noqa: E402

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def tool_names(defs):
    return {d["function"]["name"] for d in defs}


def main() -> None:
    hints = CAP.route_hints_for_capabilities(list(CAP.CAPABILITIES))
    check("every capability has route metadata",
          set(hints["capabilities"]) == set(CAP.CAPABILITIES),
          str(set(CAP.CAPABILITIES) - set(hints["capabilities"])))

    unknown = CAP.route_hints_for_capabilities(["not_a_capability"])
    check("unknown capability ids are ignored safely", unknown["capabilities"] == [], str(unknown))

    browser_defs = TD.tool_definitions("회사 포털 공지 처리", capability_ids=["browser_automation"])
    browser_tools = tool_names(browser_defs)
    check("browser capability exposes browser tools without keyword dependency",
          {"read_web_page", "browser_action", "snapshot"} <= browser_tools,
          str(sorted(browser_tools)))

    mail_defs = TD.tool_definitions("중요도별 정리", capability_ids=["web_mail_assistant"])
    mail_tools = tool_names(mail_defs)
    check("mail capability exposes browser and outlook tools",
          {"read_web_page", "outlook_app"} <= mail_tools,
          str(sorted(mail_tools)))

    matlab_defs = TD.tool_definitions("후처리 실행", capability_ids=["matlab_automation"])
    check("matlab capability exposes matlab_run", "matlab_run" in tool_names(matlab_defs))

    check("capability can drive web skill routing",
          SR.detect_skill("회사 포털 공지 처리", capability_ids=["browser_automation"]) == "웹")
    check("capability can drive macro skill routing",
          SR.detect_skill("좌표계 자동화", capability_ids=["office_cad_automation"]) == "매크로")
    check("capability can drive report skill routing",
          SR.detect_skill("정리", capability_ids=["meeting_minutes"]) == "보고서")

    ctx = SR.context_for_prompt("정리", capability_ids=["meeting_minutes"])
    check("skill context accepts capability ids", ctx and "결론 먼저" in ctx, str(ctx)[:80])

    print(f"\nALL {PASS} CHECKS PASSED (routing alignment)")


if __name__ == "__main__":
    main()
