# -*- coding: utf-8 -*-
"""활동 자동 적재 + 우선순위 인식 캡 검증.

핵심: 작업이 자동으로 기억→위키에 정리되되, 활동 홍수가 사용자 규칙을 밀어내지 않고
recall 회상에서도 규칙이 우선한다(기억이 쌓여도 효율/정확도 유지)."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

import agent_ops.memory_manager as M  # noqa: E402

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
    tmp = Path(tempfile.mkdtemp())
    M.MEMORY = tmp
    M.MEMORY_JSONL = tmp / "memory.jsonl"

    # 우선순위 보호: 사용자 규칙이 활동보다 훨씬 높게 보호됨
    a_rank = M._protect_rank({"kind": "activity", "source": "agent", "priority": "low"})
    u_rank = M._protect_rank({"kind": "preference", "source": "user", "priority": "high"})
    check("사용자 규칙이 활동보다 보호 우선", a_rank < u_rank, f"{a_rank} vs {u_rank}")

    # 활동 자동 적재 + 같은날 중복 무시 + 빈 작업 무시
    check("활동 적재됨", M.add_activity("보고서 작성", "산출물 1건") is not None)
    check("같은날 같은작업 중복 무시", M.add_activity("보고서 작성", "재시도") is None)
    check("빈 작업 무시", M.add_activity("") is None)

    # 사용자 규칙 추가 후 recall 이 규칙을 최상위로
    M.add_memory_event("preference", "결재 규칙", "부서장 결재 필수",
                       source="user", priority="high", tags=["결재", "보고서"])
    rec = M.recall(keywords=["보고서"], limit=3)
    check("recall 최상위가 사용자 규칙", rec and rec[0]["kind"] == "preference", str([r["kind"] for r in rec]))

    # 캡 시뮬: 활동 600개를 부어도 사용자 규칙은 active 로 살아남는다
    for i in range(600):
        M.add_memory_event("activity", f"작업{i}", "", priority="low", source="agent")
    active = M.load_memory(status="active")
    user_rules = [r for r in active if r.get("source") == "user"]
    check("활동 홍수에도 사용자 규칙 생존", len(user_rules) >= 1, f"active={len(active)}")
    check("active 상한 유지(<=500)", len(active) <= 500, str(len(active)))

    print(f"\nALL {PASS} CHECKS PASSED (memory activity)")


if __name__ == "__main__":
    main()
