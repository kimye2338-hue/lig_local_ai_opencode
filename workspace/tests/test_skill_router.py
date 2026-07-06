# -*- coding: utf-8 -*-
"""프로세스 스킬 자동 라우팅 검증 — 작업 유형에 맞는 절차가 자동 주입."""
from __future__ import annotations

import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

from agent_ops import skill_router as SR  # noqa: E402

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def main() -> None:
    cases = {
        "엑셀 매크로 만들어줘": "매크로",
        "솔리드웍스 매크로 작성": "매크로",
        "이 CSV 데이터 분석해줘": "데이터 분석",
        "사내 포털 공지 요약": "웹",
        "자꾸 오류 나는데 고쳐줘": "문제 해결",
        "회의록 보고서 작성해줘": "보고서",
    }
    for prompt, expect in cases.items():
        check(f"라우팅: {prompt} → {expect}", SR.detect_skill(prompt) == expect, str(SR.detect_skill(prompt)))

    check("비작업 문장은 주입 없음", SR.context_for_prompt("안녕") is None)

    ctx = SR.context_for_prompt("솔리드웍스 매크로 만들어줘")
    check("매크로 절차 주입에 공식API 원칙 포함", ctx and "공식 API 근거" in ctx, str(ctx)[:80])
    check("주입은 한 섹션(유계)", ctx and len(ctx) < 1400, str(len(ctx or "")))

    check("보고서 절차에 결론먼저", "결론 먼저" in (SR.context_for_prompt("보고서 써줘") or ""))
    check("문제해결 절차에 진단먼저", "진단 파일 먼저" in (SR.context_for_prompt("에러 고쳐줘") or ""))

    print(f"\nALL {PASS} CHECKS PASSED (skill router)")


if __name__ == "__main__":
    main()
