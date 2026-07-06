# -*- coding: utf-8 -*-
"""회상 보장 회귀 — "기억해놓으면 꼭 회상이 되도록".

Run: py -3.11 tests\\test_recall_guarantee.py  (리눅스에서도 동작 — stdlib only)

검증:
  1. 사용자 규칙(source=user)은 작업 키워드와 겹치지 않아도 항상 주입된다.
  2. 최근 실수 교훈(error_pattern)도 항상 주입된다.
  3. 에이전트 루프가 비정상 종료하면 그 패턴이 자동으로 기억에 남고,
     '다음' 루프에서 곧바로 회상된다 (시행착오의 기계적 학습).
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))

TMP = Path(tempfile.mkdtemp(prefix="recall_guarantee_"))
os.environ["AGENTOPS_ROOT"] = str(TMP / "ws")
(TMP / "ws").mkdir(parents=True, exist_ok=True)
for key in ("AGENTOPS_MEMORY_DIR", "AGENTOPS_PROJECT_DIR", "LIG_STATE_DIR"):
    os.environ.pop(key, None)

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
    from agent_ops.memory_manager import add_memory_event, add_user_memory, pinned_recall
    from agent_ops.tool_dispatch import run_agent_loop

    # 1. 사용자 규칙 — 키워드가 전혀 다른 작업에서도 주입돼야 한다.
    add_user_memory("보고서 제목은 항상 [부서명] 으로 시작한다")
    add_memory_event("error_pattern", "원본 파일 직접 수정 실수",
                     "원본 xlsx 를 직접 고쳐 데이터가 손상됐다 — 항상 사본에서",
                     source="self_observed")
    pinned = pinned_recall()
    check("pinned includes user rule", any("부서명" in str(r.get("body")) for r in pinned), str(pinned))
    check("pinned includes recent error lesson",
          any(r.get("kind") == "error_pattern" for r in pinned))

    captured = {}

    def transport(url, payload, headers, timeout):
        captured["messages"] = payload["messages"]
        return {"choices": [{"message": {"content": "끝"}}]}

    env = {"LIG_GATEWAY_BASE_URL": "http://127.0.0.1:9", "LIG_API_KEY": "x"}
    run_agent_loop("날씨 사진 정리해줘", TMP / "ws", env=env, transport=transport,
                   diag_dir=TMP / "diag")  # 기억과 무관한 키워드
    sys_texts = " ".join(m["content"] for m in captured["messages"] if m["role"] == "system")
    check("unrelated task still recalls user rule", "부서명" in sys_texts, sys_texts[:200])
    check("unrelated task still recalls error lesson", "사본에서" in sys_texts)

    # 3. 루프 실패 → 자동 기억 → 다음 루프에서 회상.
    def failing_transport(url, payload, headers, timeout):
        return {"choices": [{"message": {"content": "",
                "tool_calls": [{"function": {"name": "read_file",
                                             "arguments": '{"path": "없는파일.txt"}'}}]}}]}

    r = run_agent_loop("없는 파일 읽기 시도", TMP / "ws", env=env,
                       transport=failing_transport, diag_dir=TMP / "diag", max_turns=6)
    check("repeated failure cuts off", r["outcome"] == "tool_loop_cutoff", str(r["outcome"]))
    from agent_ops.memory_manager import load_memory
    lessons = [m for m in load_memory(status="active")
               if "tool_loop_cutoff" in str(m.get("title"))]
    check("loop failure recorded as self error", len(lessons) == 1, str(lessons))

    captured.clear()
    run_agent_loop("완전히 다른 새 작업", TMP / "ws", env=env, transport=transport,
                   diag_dir=TMP / "diag")
    sys_texts = " ".join(m["content"] for m in captured["messages"] if m["role"] == "system")
    check("next run recalls the failure lesson", "tool_loop_cutoff" in sys_texts, sys_texts[:300])

    print(f"\nALL {PASS} CHECKS PASSED (recall guarantee)")


if __name__ == "__main__":
    main()
